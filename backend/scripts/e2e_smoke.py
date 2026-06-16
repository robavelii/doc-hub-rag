#!/usr/bin/env python3
"""
Standalone E2E smoke test — exercises all major endpoints without pytest.

Usage:
  cd backend && source .venv/bin/activate
  python scripts/e2e_smoke.py

Requires Postgres, Redis, MinIO running and migrations applied.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from tests.e2e.helpers import (
    SAMPLE_DOC,
    auth_headers,
    ingest_text_sync,
    parse_sse_events,
    unique_email,
)

PASS = 0
FAIL = 0


def ok(name: str):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def fail(name: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


async def run():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        print("\n=== Health ===")
        r = await client.get("/health")
        if r.status_code == 200:
            ok("GET /health")
        else:
            fail("GET /health", r.text)

        print("\n=== Auth ===")
        email = unique_email("smoke")
        r = await client.post(
            "/auth/register",
            json={"tenant_name": "Smoke Test Co", "email": email, "password": "smoke123"},
        )
        if r.status_code == 200 and "access_token" in r.json():
            ok("POST /auth/register")
            data = r.json()
            token = data["access_token"]
            api_key = data["api_key"]
            tenant_id = data["tenant"]["id"]
        else:
            fail("POST /auth/register", r.text)
            return

        r = await client.post("/auth/login", json={"email": email, "password": "smoke123"})
        if r.status_code == 200:
            ok("POST /auth/login")
        else:
            fail("POST /auth/login", r.text)

        print("\n=== Documents + Ingestion ===")
        try:
            doc_id = ingest_text_sync(tenant_id, "smoke-doc.txt", SAMPLE_DOC)
            r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
            if r.status_code == 200 and r.json()["status"] == "ready":
                ok("Document ingest + GET /documents/{id}")
            else:
                fail("Document ingest", r.text)
        except Exception as e:
            fail("Document ingest", str(e))

        r = await client.get("/documents", headers=auth_headers(token))
        if r.status_code == 200:
            ok("GET /documents")
        else:
            fail("GET /documents", r.text)

        print("\n=== Query ===")
        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "What is Acme's refund policy?"},
        )
        if r.status_code == 200 and "answer" in r.json():
            ok("POST /query")
            print(f"         Answer preview: {r.json()['answer'][:120]}...")
        else:
            fail("POST /query", r.text)

        async with client.stream(
            "POST",
            "/query/stream",
            headers=auth_headers(token),
            json={"question": "When was Acme founded?"},
        ) as stream:
            body = await stream.aread()
            events = parse_sse_events(body.decode())
            if any(e.get("type") == "done" for e in events):
                ok("POST /query/stream (SSE)")
            else:
                fail("POST /query/stream", "no done event")

        print("\n=== Usage ===")
        r = await client.get("/usage/summary", headers=auth_headers(token))
        if r.status_code == 200:
            ok("GET /usage/summary")
        else:
            fail("GET /usage/summary", r.text)

        r = await client.get("/usage/history", headers=auth_headers(token))
        if r.status_code == 200:
            ok("GET /usage/history")
        else:
            fail("GET /usage/history", r.text)

        print("\n=== Widget ===")
        r = await client.get("/widget/config", headers={"X-API-Key": api_key})
        if r.status_code == 200:
            ok("GET /widget/config")
        else:
            fail("GET /widget/config", r.text)

        print("\n=== Admin ===")
        r = await client.post(
            "/auth/login",
            json={"email": settings.SUPERADMIN_EMAIL, "password": settings.SUPERADMIN_PASSWORD},
        )
        if r.status_code == 200:
            admin_token = r.json()["access_token"]
            r = await client.get("/admin/tenants", headers=auth_headers(admin_token))
            if r.status_code == 200:
                ok("GET /admin/tenants")
            else:
                fail("GET /admin/tenants", r.text)
        else:
            fail("Admin login (run seed.py first)", r.text)

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
