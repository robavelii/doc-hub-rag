# Doc-Hub — rules for Claude

Multi-tenant RAG SaaS: tenants upload documents and get a private, cited AI assistant (dashboard, embeddable widget, API).
README.md is the user-facing manual; this file is the working rules. When they disagree, the code wins — fix the doc.

## Layout

```
backend/app/
  routers/      HTTP endpoints (thin: validate, authorize, call a service)
  services/     business logic (query_service, retrieval, vector_service, access, polis, billing, audit…)
  providers/    AI providers: openai | ollama | local (fastembed) | mock, plus fallback chain + factory
  workers/      Celery: ingest_task, sync_task (Notion), retention_task; parsers/ per file format
  models/       SQLAlchemy models (must match migrations — CI runs `alembic check`)
  middleware/   rate limiter, security headers, logging, error handler
backend/migrations/versions/   Alembic, numbered 001_… 011_… (next: 012_)
backend/evals/                 retrieval eval corpora, questions, baselines/local.json
backend/tests/{unit,security,integration,e2e}
frontend/{dashboard,landing,widget,admin,shared}   Vite + React + strict TS; shared types in frontend/shared/types.ts
deploy/                        reverse-proxy config (see Deployment — the nginx file is NOT what the server uses)
docker-compose.dev.yml         infra only (Postgres+pgvector, Redis, SeaweedFS S3) for local dev
docker-compose.prod.yml        full stack, reads .env.prod
```

Superadmin UI lives in the dashboard (`/admin/*`, `SuperAdminRoute`). `frontend/admin` is a separate legacy app: built in CI, not deployed. Don't add features to it.

## Non-negotiable invariants

These are what the merged PRs (#2, #5, #6, #7) established. A change that weakens one needs an explicit decision from the user.

1. **Tenant isolation, three layers.** Every query on tenant data filters by `tenant_id`; Postgres RLS (`FORCE ROW LEVEL SECURITY`) on tenant tables; S3 keys prefixed `{tenant_id}/`. New tenant-owned tables get RLS in their migration and an RLS test in `tests/integration/test_rls.py`. The app connects as `app_user` (non-superuser); only migrations use `postgres`.
2. **One access scope per caller** (`services/access.py`) filters vector search, full-text search, document list/get/chunks, *and* the answer-cache key. Any new read path over documents/chunks must apply it. `collection_ids` on a query may only narrow scope, never widen.
3. **Key kinds.** `sk_` = full tenant API, server-side only. `pk_` = `/query`, `/query/stream`, `/widget/config` only, domain allowlist + per-visitor rate limit, never touches stored conversations. Keys are stored as SHA-256 hashes.
4. **Roles.** Only owner/admin (or `sk_`) upload, re-ingest, move, delete documents. Conversations are private to their creator — owners can't read members' chats.
5. **SSO/SCIM guards.** IdP may only sign in addresses on the tenant's claimed domains; never attaches an account in another tenant; owner keeps password login; SCIM can't touch the owner or other tenants. Polis webhooks are HMAC-verified with a 5-minute window.
6. **Exactly one embedding provider.** No silent fallback to mock vectors; vectors from different models never mix. Changing `EMBEDDING_PROVIDER`/`EMBEDDING_DIMENSIONS` means a migration-compatible dimension and a re-embed (`scripts/reembed_documents.py`).
7. **Citations.** The model cites `[1]..[n]`; the server rewrites to `[source:<chunk_id>]` (including across stream deltas). Frontends depend on that format.
8. **Audit + retention.** Security-relevant actions write an audit entry (`services/audit_service.py`). Retention purges content and audit rows only — never documents or billing/usage records. `audit_retention_days` ≥ 90.
9. **Production guard.** `utils/production_guard.py` refuses to boot with dev secrets when `APP_ENV=production`. Don't add defaults that bypass it; `seed.py` never creates demo tenants in production.

## Working rules

- **Branch + PR for every change**; merge only when the single `ci-ok` check is green (not enforced by branch protection yet). Conventional commit subjects (`feat(scope):`, `fix(security):`, `ci:` …). PR bodies follow the existing style: what changed and why, measured numbers for retrieval changes, tests added.
- **Tests come with the change.** Endpoint/permission changes → e2e test in `tests/e2e/` (see `test_access_control.py`, `test_collections.py` for the pattern). Parsers → unit tests building files in memory. Security helpers → `tests/security/`.
- **Retrieval/chunking/prompt changes must run the eval** and report the table in the PR. CI fails on a >0.02 drop in hit@k or MRR vs `evals/baselines/local.json`. Update the baseline only when a change is an intended improvement, and say so in the PR.
- **Schema changes** = model edit + new numbered migration in the same PR; `alembic check` must be clean. Migrations must run from an empty DB and be safe on a populated one (prod has data).
- **Dependencies**: edit `requirements.in` / `requirements-dev.in`, then recompile with `uv pip compile requirements.in -o requirements.txt --python-version 3.11` (same for dev). Never hand-edit lockfiles. `pip-audit --strict` and `npm audit --audit-level=high` must pass.
- **Python 3.11** (Dockerfile + CI). Node 20 in frontend images. Ruff config in `backend/pyproject.toml` (line length 120, security rules on).
- Routers stay thin; logic goes in `services/`. Match existing comment density: comments explain *why*, not what.
- Config is env-only via `app/config.py` `Settings`. New settings go in `config.py`, `.env.example` (with a comment), and the prod guard if they are secrets.
- Don't commit `.env*` (except `.env.example`), `dump.rdb`, `celerybeat-schedule*`, model caches, or eval `results/`.

## Commands

```bash
# local infra + backend
docker compose -f docker-compose.dev.yml up -d
cd backend && python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head && python scripts/seed.py
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker -l info   # needed for uploads

# checks (what CI runs)
ruff check app tests scripts
pytest tests/unit tests/security -q
pytest tests/integration -m integration -q        # needs Postgres, runs as app_user
pytest -m e2e -q                                  # needs Postgres, Redis, S3
EMBEDDING_PROVIDER=local EMBEDDING_DIMENSIONS=384 RERANKER=local \
  python -m evals.run_eval --check evals/baselines/local.json
cd frontend/<app> && npm ci && npm run typecheck && npm test && npm run build
```

`REQUIRE_SERVICES=1` turns "service unreachable" skips into failures — use it when you claim e2e passed.

## Deployment — shared OCI server

Target: `ubuntu@51.170.178.91` (`ssh -i ~/.ssh/oci_appt_deploy`). Ubuntu 22.04, **arm64**, 2 vCPU, ~11.6 GB RAM, **no swap**, ~25 GB free disk. Passwordless sudo.

**This host runs other people's/projects' production and staging. Rules:**

- **Never stop, restart, rebuild, prune or reconfigure anything that isn't Doc-Hub.** Other compose projects: `appt` (`/opt/appt`, project `deploy`), `escrow` (`/opt/escrow`), `job-hunter` (`/opt/job-hunter`); systemd `clipsync` (`/opt/clipsync`), `caddy`.
- **No global Docker commands**: no `docker system prune`, `docker volume prune`, `docker image prune -a`, `docker compose down` without `-p doc-hub`/the doc-hub file, no restarting the Docker daemon. Clean up only images/volumes named `doc-hub*`/`doc_hub*`.
- Always run compose with an explicit project and file: `docker compose -p doc-hub -f docker-compose.prod.yml …`. Containers are named `doc_hub_*`.
- **Reverse proxy is the shared Caddy**, not nginx. Doc-Hub adds exactly one file, `/etc/caddy/sites/doc-hub.caddy`, then `sudo -u caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && sudo systemctl reload caddy` (reload, never restart). Validate **as the caddy user**: a root validate creates `/var/log/caddy/*.log` owned by root, the real reload then fails, and a site file Caddy can't load breaks the *next* reload of every other app on the host — on failure, remove/restore the file immediately. Never edit `Caddyfile` or other site files. `deploy/nginx/doc-hub.conf` is legacy reference only.
- **Ports already taken on loopback/public**: 22, 80, 443, 111, 2019 (Caddy admin), 3001 (appt), 8090 + 8180 (escrow), 8787 (clipsync). Doc-Hub owns `127.0.0.1:8100` API, `8101` landing, `8102` dashboard, `8103` widget, `8104` Polis. Postgres/Redis/SeaweedFS (`s3` service) publish no host ports; use `docker exec` for one-off access.
- **Deploy = `scripts/deploy_oci.sh [ref]`** (also run by `.github/workflows/deploy.yml`). It ships a `git archive` to `/opt/doc-hub/releases/<sha>`, backs up the DB, builds at low priority, warms the model cache, `up -d`, health-checks, installs `deploy/caddy/doc-hub.caddy` if it changed (validate → reload, restore on failure). Change deploy behaviour there, not by hand on the server.
- Public URL `https://doc.rfh.et` (A record, DNS only; Caddy holds a Let's Encrypt cert): `/` landing, `/app/` dashboard, `/api/*` API (prefix stripped), `/widget/*`. `/api/metrics` is blocked publicly.
- **AI in production**: embeddings are local (`EMBEDDING_PROVIDER=local`, 384 dims) so the chat provider can be switched via `.env.prod` (`CHAT_PROVIDER_CHAIN` of `gemini|openai|compatible|ollama|mock`) without re-indexing. Changing embeddings needs migration 002's dimension logic plus a full re-embed — treat it as a migration project.
- **Memory budget**: other apps use ~2 GB; keep Doc-Hub's total container limits ≤ ~6 GB so the box never OOMs (no swap). Local embedding + reranker models load per process (each gunicorn worker and each Celery worker), so size workers accordingly.
- Images must build for **arm64** (build on the server, or `docker buildx --platform linux/arm64`). Check any new base image has an arm64 variant.
- App directory: `/opt/doc-hub` (owned by `ubuntu`), secrets in `/opt/doc-hub/.env.prod` (chmod 600, never committed, never echoed into logs or PRs).
- Before every deploy: `pg_dump` the doc-hub database. Migrations run via the `migrate` one-shot service before the backend starts.
- Don't open firewall ports; 80/443 are already open and Caddy terminates TLS. DNS for `rfh.et` and `robelfekadu.com` is on Cloudflare.
- Confirm with the user before: first deploy, DNS changes, adding GitHub secrets, anything that touches shared infra.

## Status (2026-11-04)

Merged to `main` (all on 2026-11-01): #1 CI gate + CVE upgrades · #2 Phase 0 security/correctness · #3 evals, hybrid search, rerank, citations · #4 structure-aware chunking + 7 formats · #5 collections/groups/permission-aware retrieval · #6 SSO/SCIM via Ory Polis · #7 audit export + retention.

In progress (`feat/deploy-oci-switchable-llm`): switchable chat providers (OpenAI / Gemini / any OpenAI-compatible), OCI deploy (Caddy site, `.env.prod` template, deploy script + workflow).

Not done yet: scheduled pg_dump + S3 (SeaweedFS volume) backups (deploy only dumps before each release), README cleanup (references missing `DEPLOYMENT.md` / `docs/LAUNCH_CHECKLIST.md`, inconsistent demo passwords), retiring `frontend/admin`.
