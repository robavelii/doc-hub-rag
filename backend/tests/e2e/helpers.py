"""Shared helpers for E2E API tests."""
import io
import uuid
from typing import Any

from httpx import AsyncClient

from app.workers.ingest_task import ingest_notion_page

SAMPLE_DOC = (
    "Acme Corporation was founded in 2010. "
    "Acme offers 24/7 customer support and a 30-day refund policy. "
    "The Pro plan includes 10GB storage and priority support."
)

OTHER_TENANT_DOC = (
    "Globex Industries specializes in financial analytics. "
    "Globex revenue in 2024 exceeded 50 million dollars. "
    "This information is confidential to Globex only."
)


def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


async def register_tenant(
    client: AsyncClient,
    tenant_name: str,
    email: str,
    password: str = "testpass12345",
) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={"tenant_name": tenant_name, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def login(client: AsyncClient, email: str, password: str = "testpass12345") -> dict[str, Any]:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def ingest_text_sync(tenant_id: str, filename: str, text: str) -> str:
    """Create and ingest a document synchronously (no Celery worker needed)."""
    import uuid as _uuid

    from app.database import SyncSession, set_tenant_rls_sync
    from app.models.document import Document

    doc_id = _uuid.uuid4()
    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename=filename,
            file_type="txt",
            s3_key="",
            status="pending",
            metadata_={"e2e": True},
        )
        db.add(doc)
        db.commit()

    ingest_notion_page.apply(args=[str(doc_id), tenant_id, text, filename])
    return str(doc_id)


def parse_sse_events(body: str) -> list[dict[str, Any]]:
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            import json

            events.append(json.loads(line[6:]))
    return events


async def upload_txt_file(
    client: AsyncClient,
    token: str,
    filename: str,
    content: str,
) -> dict[str, Any]:
    file_bytes = content.encode("utf-8")
    response = await client.post(
        "/documents",
        headers=auth_headers(token),
        files={"file": (filename, io.BytesIO(file_bytes), "text/plain")},
    )
    return response
