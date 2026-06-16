from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _derive_admin_sync_url(sync_url: str) -> str:
    """Build postgres superuser URL from app sync URL when admin URL not set."""
    parsed = urlparse(sync_url)
    # postgresql://user:pass@host:port/db -> replace user/pass with postgres defaults
    admin_netloc = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
    password = settings.POSTGRES_PASSWORD
    admin_netloc = f"postgres:{password}@{admin_netloc}"
    return urlunparse(parsed._replace(netloc=admin_netloc))


def _sync_to_async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


ADMIN_SYNC_URL = settings.DATABASE_ADMIN_SYNC_URL or _derive_admin_sync_url(settings.DATABASE_SYNC_URL)
ADMIN_ASYNC_URL = settings.DATABASE_ADMIN_URL or _sync_to_async_url(ADMIN_SYNC_URL)

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.DATABASE_SYNC_URL, echo=False, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

admin_engine = create_async_engine(ADMIN_ASYNC_URL, echo=False, pool_pre_ping=True)
AdminAsyncSessionLocal = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)

admin_sync_engine = create_engine(ADMIN_SYNC_URL, echo=False, pool_pre_ping=True)
AdminSyncSessionLocal = sessionmaker(bind=admin_sync_engine, autocommit=False, autoflush=False)


@event.listens_for(Session, "after_begin")
def _apply_rls_on_transaction_begin(session, transaction, connection) -> None:
    """Re-apply tenant RLS context at the start of every transaction (survives commit)."""
    tenant_id = session.info.get("tenant_id")
    if tenant_id:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )


def bind_tenant(session, tenant_id: str) -> None:
    """Bind tenant to session; RLS auto-reapplied on each new transaction."""
    session.info["tenant_id"] = str(tenant_id)


def clear_tenant(session) -> None:
    session.info.pop("tenant_id", None)


async def set_tenant_rls(session: AsyncSession, tenant_id: str) -> None:
    bind_tenant(session, tenant_id)
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def set_tenant_rls_sync(session, tenant_id: str) -> None:
    bind_tenant(session, tenant_id)
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_admin_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Privileged session (postgres superuser) for cross-tenant bootstrap reads."""
    async with AdminAsyncSessionLocal() as session:
        yield session


@contextmanager
def SyncSession() -> Generator:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def AdminSyncSession() -> Generator:
    session = AdminSyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
