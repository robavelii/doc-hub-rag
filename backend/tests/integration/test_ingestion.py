"""Integration test for ingestion pipeline."""

import uuid

import pytest
from unittest.mock import patch

from app.database import AdminSyncSession, SyncSession, set_tenant_rls_sync
from app.models.document import Document
from app.models.tenant import Tenant
from app.services.auth_service import api_key_prefix, generate_api_key, hash_api_key, slugify
from app.workers.ingest_task import ingest_notion_page

pytestmark = pytest.mark.integration

SAMPLE = (
    "Doc-Hub ingestion test document. "
    "Acme Corporation offers 24/7 support and a 30-day refund policy."
)


@pytest.fixture(scope="session")
def postgres_available():
    try:
        from sqlalchemy import create_engine, text
        from app.config import settings

        engine = create_engine(settings.DATABASE_SYNC_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Integration tests require Postgres")


@pytest.fixture
def tenant_id(postgres_available):
    raw_key = generate_api_key()
    tid = uuid.uuid4()
    with AdminSyncSession() as db:
        tenant = Tenant(
            id=tid,
            name=f"Ingest Test {tid.hex[:6]}",
            slug=slugify(f"ingest-{tid.hex[:6]}"),
            api_key_hash=hash_api_key(raw_key),
            api_key_prefix=api_key_prefix(raw_key),
        )
        db.add(tenant)
        db.commit()
    yield str(tid)
    with AdminSyncSession() as db:
        tenant = db.get(Tenant, tid)
        if tenant:
            db.delete(tenant)
            db.commit()


def test_ingest_notion_page_reaches_ready(tenant_id):
    doc_id = uuid.uuid4()

    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        doc = Document(
            id=doc_id,
            tenant_id=uuid.UUID(tenant_id),
            filename="ingest-test.txt",
            file_type="txt",
            s3_key="",
            status="pending",
        )
        db.add(doc)
        db.commit()

    with patch("app.workers.ingest_task.embed_chunks", return_value=[[0.1] * 768]):
        ingest_notion_page.apply(args=[str(doc_id), tenant_id, SAMPLE, "ingest-test.txt"])

    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        doc = db.get(Document, doc_id)
        assert doc is not None
        assert doc.status == "ready"
        assert doc.chunk_count >= 1

        db.delete(doc)
        db.commit()
