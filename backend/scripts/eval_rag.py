"""Evaluate RAG answer quality against expected substrings.

Usage:
  cd backend && source .venv/bin/activate
  python scripts/eval_rag.py
  EVAL_TENANT_ID=<uuid> python scripts/eval_rag.py

Requires ingested documents and a working chat provider (OpenAI key recommended).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import AsyncSessionLocal, set_tenant_rls
from app.models.tenant import Tenant
from app.services.query_service import complete_rag_query, run_rag_query

# Smoke cases against the seeded Acme demo tenant (scripts/seed.py).
# Phase 1 replaces this with a proper multi-corpus eval harness.
EVAL_CASES: list[tuple[str, str]] = [
    ("what is the refund policy", "30 days"),
    ("how long do I have to return a product", "30"),
    ("is support available on weekends", "24/7"),
    ("how much storage does the free plan include", "100MB"),
    ("what does the pro plan include", "10GB"),
]


async def _resolve_tenant_id() -> str | None:
    explicit = os.environ.get("EVAL_TENANT_ID", "").strip()
    if explicit:
        return explicit
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
        return str(tenant.id) if tenant else None


async def _run_case(tenant_id: str, question: str, expected: str) -> bool:
    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, tenant_id)
        context = await run_rag_query(question, tenant_id, db)
        if "answer" in context:
            answer = context["answer"]
        else:
            result = await complete_rag_query(context, tenant_id, db)
            answer = result["answer"]

    ok = expected.lower() in answer.lower()
    status = "PASS" if ok else "FAIL"
    preview = answer[:120].replace("\n", " ")
    print(f"{status}: {question!r}")
    print(f"       expected: {expected!r}")
    print(f"       got:      {preview!r}...")
    return ok


async def main() -> None:
    tenant_id = await _resolve_tenant_id()
    if not tenant_id:
        print("No tenant found. Register a user or set EVAL_TENANT_ID.")
        sys.exit(1)

    print(f"Evaluating tenant {tenant_id} ({len(EVAL_CASES)} cases)\n")
    passed = 0
    for question, expected in EVAL_CASES:
        if await _run_case(tenant_id, question, expected):
            passed += 1
        print()

    print(f"Result: {passed}/{len(EVAL_CASES)} passed")
    sys.exit(0 if passed == len(EVAL_CASES) else 1)


if __name__ == "__main__":
    asyncio.run(main())
