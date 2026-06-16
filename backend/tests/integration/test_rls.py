"""RLS regression tests — require Postgres with app_user role (migration 004)."""

import uuid

import pytest
from sqlalchemy import select, text

from app.config import settings
from app.database import (
    AdminSyncSession,
    AsyncSessionLocal,
    SyncSession,
    bind_tenant,
    set_tenant_rls,
    set_tenant_rls_sync,
)
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.services.auth_service import api_key_prefix, generate_api_key, hash_api_key, slugify
from app.services.usage_service import record_storage_usage

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_available():
    try:
        from sqlalchemy import create_engine

        engine = create_engine(settings.DATABASE_SYNC_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Integration tests require Postgres")


@pytest.fixture(scope="session")
def app_user_available(postgres_available):
    if "app_user" not in settings.DATABASE_SYNC_URL:
        pytest.skip("RLS tests require DATABASE_SYNC_URL with app_user")


def _create_tenant() -> uuid.UUID:
    raw_key = generate_api_key()
    tid = uuid.uuid4()
    with AdminSyncSession() as db:
        tenant = Tenant(
            id=tid,
            name=f"RLS Test {tid.hex[:6]}",
            slug=slugify(f"rls-test-{tid.hex[:6]}"),
            api_key_hash=hash_api_key(raw_key),
            api_key_prefix=api_key_prefix(raw_key),
        )
        db.add(tenant)
        db.commit()
    return tid


def _delete_tenant(tid: uuid.UUID) -> None:
    with AdminSyncSession() as db:
        tenant = db.get(Tenant, tid)
        if tenant:
            db.delete(tenant)
            db.commit()


@pytest.fixture
def tenant_id(app_user_available):
    tid = _create_tenant()
    yield str(tid)
    _delete_tenant(tid)


@pytest.fixture
def second_tenant_id(app_user_available):
    tid = _create_tenant()
    yield str(tid)
    _delete_tenant(tid)


@pytest.mark.asyncio
async def test_rls_survives_commit_for_usage_events(tenant_id):
    ref_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, tenant_id)
        doc = Document(
            tenant_id=uuid.UUID(tenant_id),
            filename="rls-test.txt",
            file_type="txt",
            s3_key="",
            size_bytes=100,
            status="pending",
        )
        db.add(doc)
        await db.commit()

        await record_storage_usage(tenant_id, 100, ref_id, db)

        result = await db.execute(
            select(UsageEvent).where(UsageEvent.ref_id == uuid.UUID(ref_id))
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.storage_delta_bytes == 100

        await db.delete(doc)
        await db.commit()


@pytest.mark.asyncio
async def test_bind_tenant_reapplies_after_commit(tenant_id):
    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, tenant_id)

        doc = Document(
            tenant_id=uuid.UUID(tenant_id),
            filename="bind-test.txt",
            file_type="txt",
            s3_key="",
            status="pending",
        )
        db.add(doc)
        await db.commit()

        result = await db.execute(select(Document).where(Document.filename == "bind-test.txt"))
        assert result.scalar_one_or_none() is not None

        await db.delete(doc)
        await db.commit()


def test_sync_session_rls_after_commit(tenant_id):
    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        doc = Document(
            tenant_id=uuid.UUID(tenant_id),
            filename="sync-rls.txt",
            file_type="txt",
            s3_key="",
            status="pending",
        )
        db.add(doc)
        db.commit()

        found = db.execute(select(Document).where(Document.filename == "sync-rls.txt")).scalar_one_or_none()
        assert found is not None

        db.delete(found)
        db.commit()


@pytest.mark.asyncio
async def test_cross_tenant_read_returns_nothing(tenant_id, second_tenant_id):
    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, tenant_id)
        doc = Document(
            tenant_id=uuid.UUID(tenant_id),
            filename="tenant-a-only.txt",
            file_type="txt",
            s3_key="",
            status="pending",
        )
        db.add(doc)
        await db.commit()
        doc_id = doc.id

    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, second_tenant_id)
        result = await db.execute(select(Document).where(Document.id == doc_id))
        assert result.scalar_one_or_none() is None

    async with AsyncSessionLocal() as db:
        await set_tenant_rls(db, tenant_id)
        doc = await db.get(Document, doc_id)
        if doc:
            await db.delete(doc)
            await db.commit()
