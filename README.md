# Doc-Hub

Production-grade multi-tenant SaaS where companies upload knowledge bases and get a private AI assistant. Each tenant is fully isolated.

## Stack

- **Backend:** FastAPI, Celery, SQLAlchemy, Alembic
- **Vector store:** PostgreSQL + pgvector (tenant-scoped chunks table)
- **Storage:** MinIO (S3-compatible)
- **Cache/Queue:** Redis
- **AI:** Pluggable provider layer (mock default, OpenAI optional, Ollama local fallback)
- **Frontend:** React + Vite + TypeScript (dashboard, landing page, embeddable widget; superadmin routes in dashboard)

## Quick Start

```bash
# 1. Copy environment
cp .env.example .env

# 2. Start infrastructure (dev mode - DB, Redis, MinIO only)
docker compose -f docker-compose.dev.yml up -d

# 3. Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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
| MinIO Console | http://localhost:9001 |

Superadmin routes live in the dashboard at `/admin/tenants` and `/admin/usage`.

## Production deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) and [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md).

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

1. Start all services (Postgres, Redis, MinIO, backend, Celery worker, dashboard).
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
frontend/admin/        Superadmin panel (Vite + React + TS)
```

## TypeScript

All frontends use strict TypeScript (`tsconfig.base.json`). Shared API types live in `frontend/shared/types.ts` and are imported via the `@shared` alias. Run type-check per app:

```bash
cd frontend/dashboard && npm run typecheck
cd frontend/widget && npm run typecheck
cd frontend/admin && npm run typecheck
```

## Testing

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
cd frontend/admin && npm run typecheck

# Unit tests (dashboard stream/types)
cd frontend/dashboard && npm install && npm run test

# Production builds
cd frontend/dashboard && npm run build
cd frontend/widget && npm run build
cd frontend/admin && npm run build
```

### Manual UI checklist

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open http://localhost:5173, login `demo@acme.com` / `demo123` | Dashboard loads |
| 2 | Documents page | 2 docs with status **ready** |
| 3 | Chat: "What is Acme refund policy?" | Answer mentions 30-day returns |
| 4 | Usage page | Token count > 0 after query |
| 5 | Widget page | Embed code shown |
| 6 | Admin http://localhost:5174, login as superadmin | Tenant list visible |
| 7 | Register 2nd tenant, upload doc, query | Only own docs visible |

### Celery note

File uploads via UI require a Celery worker. Seed script ingests demo docs synchronously without Celery. For uploads:

```bash
celery -A app.workers.celery_app worker --loglevel=info
```
