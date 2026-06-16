from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db_context, set_tenant_rls
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent

PLAN_LIMITS = {
    "free": {"tokens": 100_000, "storage": 100 * 1024 * 1024, "docs": 10, "rate": 10},
    "starter": {"tokens": 1_000_000, "storage": 1024 * 1024 * 1024, "docs": 100, "rate": 60},
    "pro": {"tokens": 10_000_000, "storage": 10 * 1024 * 1024 * 1024, "docs": None, "rate": 300},
}


async def get_monthly_token_usage(tenant_id: str, db: AsyncSession) -> int:
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.sum(UsageEvent.tokens))
        .where(UsageEvent.tenant_id == tenant_id)
        .where(UsageEvent.event_type == "query")
        .where(UsageEvent.occurred_at >= start_of_month)
    )
    return result.scalar() or 0


async def get_monthly_token_usage_admin(tenant_id: str) -> int:
    async with get_admin_db_context() as admin_db:
        return await get_monthly_token_usage(tenant_id, admin_db)


async def get_storage_usage(tenant_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.sum(UsageEvent.storage_delta_bytes)).where(UsageEvent.tenant_id == tenant_id)
    )
    return result.scalar() or 0


async def get_storage_usage_admin(tenant_id: str) -> int:
    async with get_admin_db_context() as admin_db:
        return await get_storage_usage(tenant_id, admin_db)


async def get_global_token_usage_admin() -> int:
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with get_admin_db_context() as admin_db:
        result = await admin_db.execute(
            select(func.sum(UsageEvent.tokens))
            .where(UsageEvent.event_type == "query")
            .where(UsageEvent.occurred_at >= start_of_month)
        )
        return result.scalar() or 0


async def check_query_limit(tenant: Tenant, db: AsyncSession) -> None:
    limit = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    used = await get_monthly_token_usage(str(tenant.id), db)
    if used >= limit["tokens"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Monthly query limit reached",
                "used": used,
                "limit": limit["tokens"],
                "upgrade_url": f"{tenant.slug}/upgrade",
            },
        )


async def check_storage_limit(tenant: Tenant, new_bytes: int, db: AsyncSession) -> None:
    current_storage = await get_storage_usage(str(tenant.id), db)
    limit = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    if (current_storage + new_bytes) > limit["storage"]:
        raise HTTPException(
            status_code=400,
            detail={"message": "Storage limit reached", "limit_bytes": limit["storage"]},
        )


async def record_query_usage(tenant_id: str, tokens: int, query_log_id: str, db: AsyncSession) -> None:
    await set_tenant_rls(db, tenant_id)
    event = UsageEvent(
        tenant_id=tenant_id,
        event_type="query",
        tokens=tokens,
        ref_id=query_log_id,
    )
    db.add(event)
    await db.commit()


async def record_storage_usage(tenant_id: str, delta_bytes: int, ref_id: str, db: AsyncSession) -> None:
    await set_tenant_rls(db, tenant_id)
    event = UsageEvent(
        tenant_id=tenant_id,
        event_type="doc_upload" if delta_bytes >= 0 else "doc_delete",
        storage_delta_bytes=delta_bytes,
        ref_id=ref_id,
    )
    db.add(event)
    await db.commit()
