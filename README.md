# Doc-Hub

Production-grade multi-tenant SaaS where companies upload knowledge bases and get a private AI assistant. Each tenant is fully isolated.

## Stack

- **Backend:** FastAPI, Celery, SQLAlchemy, Alembic
- **Vector store:** PostgreSQL + pgvector (tenant-scoped chunks table)
- **Storage:** SeaweedFS (S3-compatible, Apache-2.0; replaced MinIO, whose community images are discontinued)
- **Cache/Queue:** Redis
- **AI:** Pluggable provider layer (mock default, OpenAI optional, Ollama local fallback)
- **Frontend:** React + Vite + TypeScript (dashboard, landing page, embeddable widget; superadmin routes in dashboard)

## Quick Start

```bash
# 1. Copy environment
cp .env.example .env

# 2. Start infrastructure (dev mode - DB, Redis, SeaweedFS S3 only)
docker compose -f docker-compose.dev.yml up -d

# 3. Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload

# 4. Celery (separate terminals)
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info

# 5. Dashboard
cd frontend/dashboard && npm install && npm run dev

# 6. Landing page
cd frontend/landing && npm install && npm run dev

# 7. Widget build
cd frontend/widget && npm install && npm run build
```

Or run everything with Docker:

```bash
cp .env.example .env
docker compose --profile doc-hub up --build
```

## Services

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Dashboard | http://localhost:3000 |
| Landing | http://localhost:8080 |
| Widget CDN | http://localhost:3002/widget.js |
| S3 (SeaweedFS) | http://localhost:9000 (keys minioadmin/minioadmin) |

Superadmin routes live in the dashboard at `/admin/tenants` and `/admin/usage`.

## Production deployment

Production runs on a shared OCI host behind its Caddy at https://doc.rfh.et (`/` landing, `/app/` dashboard, `/api/` API, `/widget/widget.js`).

```bash
scripts/deploy_oci.sh --init-env   # once: writes /opt/doc-hub/.env.prod with generated secrets
scripts/deploy_oci.sh              # ship HEAD: backup, build, migrate, start, install Caddy site
```

The `Deploy` GitHub workflow runs the same script after CI passes on `main` (secrets `OCI_SSH_KEY`, `OCI_HOST`, `OCI_KNOWN_HOSTS`). Template for the server env: [deploy/env.prod.example](deploy/env.prod.example). Host rules (other apps share the machine): see CLAUDE.md.

### Switching the chat model

Chat providers are tried in `CHAT_PROVIDER_CHAIN` order; each is enabled by its key:

| Name | Settings |
|---|---|
| `openai` | `OPENAI_API_KEY`, `CHAT_MODEL`, optional `OPENAI_BASE_URL` |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_CHAT_MODEL`, `GEMINI_REASONING_EFFORT` |
| `compatible` | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHAT_MODEL` (any OpenAI-compatible API) |
| `ollama`, `mock` | see below |

Production keeps embeddings local (`EMBEDDING_PROVIDER=local`, 384 dims), so changing the chat provider is an env edit plus `docker compose -p doc-hub … up -d` with no re-indexing.

## Demo Credentials

After running `python scripts/seed.py`:

| Tenant | Email | Password |
|--------|-------|----------|
| Acme Corp | demo@acme.com | demo12345678 |
| Globex Inc | demo@globex.com | demo12345678 |
| Superadmin | admin@yoursaas.com | (from .env SUPERADMIN_PASSWORD) |

## AI Provider (Mock vs OpenAI)

### Mock mode (default — no API key needed)

```env
AI_PROVIDER=mock
```

Uses deterministic embeddings and canned chat responses. Good for local dev and running the full test suite without cost.

### OpenAI mode (real RAG with your documents)

1. Get an API key from [platform.openai.com](https://platform.openai.com/api-keys).

2. Edit `.env` (both project root and `backend/.env` if you run from there):

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...your-key-here...
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini
EMBEDDING_DIMENSIONS=768
```

3. Restart the backend (and Celery worker if running):

```bash
# Stop uvicorn, then:
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker --loglevel=info
```

4. Verify provider in health check:

```bash
curl http://localhost:8000/health
# {"status":"ok","ai_provider":"openai",...}
```

### Test with a real document (OpenAI)

**Option A — Dashboard UI**

1. Start all services (Postgres, Redis, SeaweedFS, backend, Celery worker, dashboard).
2. Register a new tenant or log in as `demo@acme.com` / `demo123`.
3. Go to **Documents** → upload a PDF, DOCX, or TXT (e.g. a company FAQ or product spec).
4. Wait for status **ready** (requires Celery worker; check Documents page).
5. Go to **Chat** → ask a specific question answerable only from that file.
6. Confirm the answer cites sources and matches your document content.

**Option B — curl**

```bash
BASE=http://localhost:8000

# Register
curl -s -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"MyCo","email":"me@test.com","password":"pass123"}' | jq .

# Save token from response
TOKEN="eyJ..."

# Upload a text file
echo "Our warranty lasts 5 years. Contact support@mycompany.com for claims." > /tmp/warranty.txt
curl -s -X POST $BASE/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/warranty.txt" | jq .

# Wait for Celery to finish (~10s), then query
curl -s -X POST $BASE/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"How long is the warranty?"}' | jq .
```

**Option C — Re-seed demo tenants (no Celery needed for seed)**

```bash
cd backend && python scripts/seed.py
# Logs in as demo@acme.com / demo123, ask "What is Acme refund policy?"
```

### OpenAI integration test (automated)

```bash
cd backend && source .venv/bin/activate
AI_PROVIDER=openai OPENAI_API_KEY=sk-... pytest tests/e2e/test_openai_integration.py -m openai -v
```

## Retrieval pipeline and evals

Questions go through: cache → follow-up condensing (rewrites "what about the second one?" using the conversation) → **hybrid retrieval** (HNSW vector search + Postgres full-text search, merged with reciprocal rank fusion) → **cross-encoder rerank** of the top candidates → prompt with numbered passages `[1]..[n]` (rewritten to `[source:<chunk_id>]` before reaching clients).

| Setting | Values | Notes |
|---|---|---|
| `EMBEDDING_PROVIDER` | `openai` · `ollama` · `local` · `mock` | Exactly one; no fallback. `local` = in-process `bge-small-en-v1.5`, 384 dims, no API key |
| `RERANKER` | `local` · `none` | `local` = MiniLM cross-encoder on CPU (~250 ms/query) |
| `RERANK_POOL` | default `10` | Candidates reranked; evals showed no gain above ~12 |

Models download on first use to `LOCAL_MODEL_CACHE_DIR` (or the fastembed default cache).

**Supported uploads:** PDF (page numbers), Word (heading styles), PowerPoint (slide titles, speaker notes), Excel and CSV (rows keep their column names), Markdown, HTML (main content only), email (.eml), plain text, and URLs. Documents are split on their headings and every chunk is prefixed with its heading path, which is also returned with sources (`heading`, `page`). Re-ingest older documents (`scripts/reembed_documents.py`) to get this metadata.

**Evals** (`backend/evals/`): 6 documents (4 with answers, 2 distractors), 114 questions (lexical, paraphrased, unanswerable), every answer tied to a verbatim evidence span. CI's `retrieval-eval` job fails a PR whose overall hit@k or MRR drops more than 0.02 below `evals/baselines/local.json`.

```bash
cd backend
EMBEDDING_PROVIDER=local EMBEDDING_DIMENSIONS=384 RERANKER=local python -m evals.run_eval
python -m evals.run_eval --check evals/baselines/local.json   # what CI runs
python -m evals.run_eval --answers                            # also grade generated answers (needs a real LLM)
```

## Local Model (Ollama)

Run a small local model for offline testing and automatic fallback when OpenAI is unavailable.

### Recommended models (lightweight)

| Role | Model | Size |
|------|-------|------|
| Chat | `llama3.2:1b` | ~1.3 GB |
| Embeddings | `nomic-embed-text` | ~274 MB |

Even lighter chat alternative: `qwen2.5:0.5b`

### Install and pull models

```bash
# Install Ollama: https://ollama.com
ollama serve   # if not already running
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```

### Configure `.env`

**Chat with local fallback (keeps OpenAI embeddings — no re-index needed):**

```env
AI_PROVIDER=mock
CHAT_PROVIDER_CHAIN=openai,ollama,mock
EMBEDDING_PROVIDER=openai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.2:1b
PROVIDER_TIMEOUT_SECONDS=30
```

**Fully local (chat + embeddings via Ollama):**

```env
AI_PROVIDER=ollama
CHAT_PROVIDER_CHAIN=ollama,mock
EMBEDDING_PROVIDER=ollama
EMBEDDING_DIMENSIONS=768
OLLAMA_CHAT_MODEL=llama3.2:1b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Then re-index (embedding dimension changes from 1536 to 768):

```bash
cd backend
alembic upgrade head   # applies 002_configurable_embedding_dim
python scripts/seed.py # re-embed demo documents
```

### Fallback chain

- **Chat:** tries providers in `CHAT_PROVIDER_CHAIN` order (default: `openai` → `ollama` → `mock`)
- **Embeddings:** uses `EMBEDDING_PROVIDER` only; on failure falls back to mock (same dimension — safe for retrieval)

### Docker with Ollama

```bash
docker compose --profile local-ai up -d ollama ollama_init
# Pull completes via ollama_init; then start backend as usual
```

Set `OLLAMA_BASE_URL=http://ollama:11434` when backend runs inside Docker.

### Verify

```bash
curl http://localhost:8000/health | jq .
# Check providers.ollama.reachable and providers.chat_provider_chain
```

Chat responses show the model used (e.g. `ollama/llama3.2:1b`) in the metrics bar.

### Local model integration test

```bash
cd backend && source .venv/bin/activate
pytest tests/e2e/test_local_model.py -m local -v
# Skips automatically if Ollama is not running
```

### Production RAG checklist (real documents)

1. **Use real embeddings + chat** — mock cannot answer questions (it dumps chunks). Set `OPENAI_API_KEY`, `EMBEDDING_PROVIDER=openai`, `CHAT_PROVIDER_CHAIN=openai,ollama,mock`, `EMBEDDING_DIMENSIONS=768` (OpenAI `text-embedding-3-small` with `dimensions=768`).
2. **Run migration + re-embed** after switching embedding provider:
   ```bash
   alembic upgrade head
   python scripts/reembed_documents.py   # requires Celery worker
   ```
3. **PDF ingestion** — scanned PDFs use Tesseract OCR fallback; tables use pdfplumber. Docker image includes `tesseract-ocr`.
4. **Verify documents** — all uploads should show status **ready** with chunk count > 0. Re-process any **failed** docs from the dashboard.
5. **Eval harness** — `python scripts/eval_rag.py` runs question/answer checks against ingested docs (requires `OPENAI_API_KEY` for best results).
6. **Health check** — `curl http://localhost:8000/health` should show `active_embedding_provider: openai` or `ollama` (not `mock`).

## API Overview

- `POST /auth/register` — Create tenant + owner user (returns API key once)
- `POST /auth/login` — JWT login
- `POST /documents` — Upload file (async ingestion)
- `POST /documents/url` — Ingest URL
- `POST /query/stream` — SSE streaming RAG query
- `GET /usage/summary` — Token/storage usage
- `GET /widget/config` — Widget settings (API key auth)
- `GET /admin/tenants` — Superadmin tenant list

### API keys

| Kind | Prefix | Can do | Where it belongs |
|------|--------|--------|------------------|
| Secret | `sk_` | Full tenant API (documents, query, conversations, usage) | Your servers only |
| Publishable | `pk_` | `POST /query`, `POST /query/stream`, `GET /widget/config` only; honours the widget domain allowlist and a per-visitor rate limit; never reads or writes stored conversations | The embeddable widget |

Registration returns one of each (`api_key`, `widget_key`). Create more in **Settings → API keys** or **Widget**. Keys are stored as SHA-256 hashes; legacy bcrypt-hashed keys keep working and are re-hashed on first use.

### Collections and groups

Documents live in **General** (whole tenant) or a **collection**. A collection is visible to everyone or **restricted** to selected groups (Settings → Access).

| Caller | Sees |
|---|---|
| Owner / admin, secret key | Everything |
| Member | General + "everyone" collections + restricted collections granted to their groups |
| Widget key scoped to a collection | Only that collection |
| Widget key, unscoped | General + "everyone" collections |

The same scope filters retrieval, document list/read and the answer cache key. `POST /query` accepts `collection_ids` (and `"general"`) to search within a subset; it can only narrow. Restricted collections cannot be deleted while they contain documents.

### Single sign-on and SCIM (Ory Polis)

Customers sign in with their own identity provider (Okta, Entra ID, Google Workspace, any SAML 2.0 or OIDC IdP) through a self-hosted [Ory Polis](https://github.com/ory/polis) (Apache-2.0), and can provision users and groups over SCIM 2.0.

1. Run Polis: `docker compose -f docker-compose.prod.yml --profile sso up -d polis` (create a `polis` database first) and set the `POLIS_*` variables in `.env` (see `.env.example`). Expose Polis to browsers at `POLIS_PUBLIC_URL`.
2. Owner, in **Settings → SSO**: connect the IdP (metadata URL; the page shows the callback URL to configure), claim email domains, optionally require SSO, and create a SCIM endpoint.
3. Users choose **Continue with SSO** on the login page. First-time users are created as members (just-in-time provisioning).

Rules: a domain belongs to one workspace; public email domains cannot be claimed; the IdP can only sign in addresses on claimed domains and never an account in another workspace; owners keep password login when SSO is enforced; SCIM can deactivate members but never the owner. SCIM groups appear in Settings → Access and can be granted restricted collections. Webhooks are verified (HMAC-SHA256, 5-minute replay window).

### Audit log and retention

- `GET /audit-logs` (newest first, filter by `action`/`since`/`until`) and `GET /audit-logs/export?format=csv|jsonl` (owner/admin; the export is itself audited). Recorded: sign-ups, logins (password and SSO), API key changes, document upload/delete/move, collection and group changes, SSO/SCIM configuration, retention changes.
- `PUT /settings/retention`: `content_retention_days` (questions, answers, conversations) and `audit_retention_days` (min 90). A nightly Celery beat job (`purge_expired_data`, 03:17 UTC) deletes older rows. Documents and billing records are never purged automatically.
- Settings → **Compliance** in the dashboard.

### Roles and privacy

- Conversations are private to the user who created them (owners cannot read members' chats).
- Only `owner` and `admin` users (or secret keys) can upload, re-ingest or delete documents; `member` users can read and ask.

## Production notes

- `scripts/seed.py` never creates the demo tenants when `APP_ENV=production` (override with `SEED_DEMO_TENANTS=true`).
- Set `FORWARDED_ALLOW_IPS` to your reverse proxy's address so per-visitor widget rate limits see real client IPs (`docker-compose.prod.yml` sets it for the host nginx setup).
- If an existing widget embed uses an old full-access key, replace it with a `pk_` key and revoke the old one.

## Tenant Isolation

1. **pgvector:** All chunk queries filter by `tenant_id`
2. **PostgreSQL RLS:** Row-level security on documents, chunks, query_logs, usage_events
3. **S3 keys:** Prefixed with `{tenant_id}/`

## Project Structure

```
backend/app/           FastAPI application
frontend/shared/       Shared TypeScript types (types.ts)
frontend/dashboard/    Tenant dashboard (Vite + React + TS)
frontend/widget/       Embeddable chat widget (Vite IIFE + TS)
frontend/landing/      Marketing landing page (Vite + React + TS)
```

## TypeScript

All frontends use strict TypeScript (`tsconfig.base.json`). Shared API types live in `frontend/shared/types.ts` and are imported via the `@shared` alias. Run type-check per app:

```bash
cd frontend/dashboard && npm run typecheck
cd frontend/widget && npm run typecheck
```

## Testing

CI (`.github/workflows/ci.yml`) runs on every pull request and gates merges through a single `ci-ok` check:

| Job | What it enforces |
|-----|------------------|
| backend · lint + dependency audit | ruff, lockfiles in sync with `requirements*.in`, `pip-audit` (no known CVEs) |
| backend · unit + security tests | `tests/unit`, `tests/security` with coverage |
| backend · migrations, integration + e2e | migrate an empty DB, `alembic check` (models match migrations), RLS tests as `app_user`, e2e with inline Celery. Missing services fail instead of skipping (`REQUIRE_SERVICES=1`) |
| frontend · dashboard/landing/widget | `npm ci`, typecheck, tests, build, `npm audit --audit-level=high` |
| docker · backend/dashboard/landing/widget | images build; backend image imports the app |

### Dependencies

Runtime deps live in `backend/requirements.in`, test/tooling deps in `backend/requirements-dev.in`. Both are compiled to fully pinned lockfiles:

```bash
cd backend
uv pip compile requirements.in -o requirements.txt --python-version 3.11
uv pip compile requirements-dev.in -o requirements-dev.txt --python-version 3.11
```

### Prerequisites

```bash
docker compose -f docker-compose.dev.yml up -d
cd backend && alembic upgrade head && python scripts/seed.py
```

### Unit tests (no external services)

```bash
cd backend && pytest tests/unit -v
```

### E2E smoke test (recommended — all major endpoints)

Covers: health, auth, documents, query + SSE stream, usage, widget config, admin.

```bash
cd backend && python scripts/e2e_smoke.py
```

### E2E pytest suite (granular tests)

```bash
cd backend && pytest tests/e2e -m e2e -v
```

Includes tenant isolation tests. Run per-class if you hit async pool warnings:

```bash
pytest tests/e2e/test_full_platform.py -v
```

### Run everything

```bash
chmod +x scripts/run_all_tests.sh
./scripts/run_all_tests.sh
```

### Frontend tests

```bash
# TypeScript type-check (all apps)
cd frontend/dashboard && npm run typecheck
cd frontend/widget && npm run typecheck

# Unit tests (dashboard stream/types)
cd frontend/dashboard && npm install && npm run test

# Production builds
cd frontend/dashboard && npm run build
cd frontend/widget && npm run build
```

### Manual UI checklist

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open http://localhost:5173, login `demo@acme.com` / `demo123` | Dashboard loads |
| 2 | Documents page | 2 docs with status **ready** |
| 3 | Chat: "What is Acme refund policy?" | Answer mentions 30-day returns |
| 4 | Usage page | Token count > 0 after query |
| 5 | Widget page | Embed code shown |
| 6 | Log in to the dashboard as superadmin, open `/admin/tenants` | Tenant list visible |
| 7 | Register 2nd tenant, upload doc, query | Only own docs visible |

### Celery note

File uploads via UI require a Celery worker. Seed script ingests demo docs synchronously without Celery. For uploads:

```bash
celery -A app.workers.celery_app worker --loglevel=info
```
