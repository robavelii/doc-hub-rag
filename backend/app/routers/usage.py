from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models.query_log import QueryLog
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.services.usage_service import PLAN_LIMITS, get_monthly_token_usage, get_storage_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary")
async def usage_summary(tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    plan_limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    tokens_used = await get_monthly_token_usage(str(tenant.id), db)
    storage_used = await get_storage_usage(str(tenant.id), db)
    token_pct = (tokens_used / plan_limits["tokens"] * 100) if plan_limits["tokens"] else 0
    warning = None
    if token_pct >= 100:
        warning = "limit_reached"
    elif token_pct >= 95:
        warning = "critical"
    elif token_pct >= 80:
        warning = "approaching"
    return {
        "plan": tenant.plan,
        "tokens_used": tokens_used,
        "tokens_limit": plan_limits["tokens"],
        "storage_used_bytes": storage_used,
        "storage_limit_bytes": plan_limits["storage"],
        "usage_warning": warning,
    }


@router.get("/history")
async def usage_history(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(QueryLog)
        .where(QueryLog.tenant_id == tenant.id)
        .order_by(QueryLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()
    count_result = await db.execute(
        select(func.count()).select_from(QueryLog).where(QueryLog.tenant_id == tenant.id)
    )
    total = count_result.scalar() or 0
    return {
        "items": [
            {
                "id": str(log.id),
                "question": log.question,
                "answer": log.answer,
                "tokens_total": log.tokens_total,
                "confidence_score": log.confidence_score,
                "from_cache": log.from_cache,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/timeseries")
async def usage_timeseries(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    range: str = Query("7d", pattern="^(7d|30d|90d)$"),
):
    days = {"7d": 7, "30d": 30, "90d": 90}[range]
    since = datetime.now(timezone.utc) - timedelta(days=days)

    token_result = await db.execute(
        select(cast(UsageEvent.occurred_at, Date).label("day"), func.sum(UsageEvent.tokens))
        .where(UsageEvent.tenant_id == tenant.id, UsageEvent.event_type == "query", UsageEvent.occurred_at >= since)
        .group_by("day")
        .order_by("day")
    )
    tokens_by_day = [{"date": str(row[0]), "tokens": row[1] or 0} for row in token_result.all()]

    query_result = await db.execute(
        select(cast(QueryLog.created_at, Date).label("day"), func.count())
        .where(QueryLog.tenant_id == tenant.id, QueryLog.created_at >= since)
        .group_by("day")
        .order_by("day")
    )
    queries_by_day = [{"date": str(row[0]), "queries": row[1] or 0} for row in query_result.all()]

    confidence_result = await db.execute(
        select(cast(QueryLog.created_at, Date).label("day"), func.avg(QueryLog.confidence_score))
        .where(QueryLog.tenant_id == tenant.id, QueryLog.created_at >= since, QueryLog.confidence_score.isnot(None))
        .group_by("day")
        .order_by("day")
    )
    confidence_by_day = [
        {"date": str(row[0]), "avg_confidence": round(float(row[1] or 0), 3)} for row in confidence_result.all()
    ]

    return {
        "range": range,
        "tokens_by_day": tokens_by_day,
        "queries_by_day": queries_by_day,
        "confidence_by_day": confidence_by_day,
    }


@router.get("/analytics")
async def usage_analytics(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    top_queries = await db.execute(
        select(QueryLog.question, func.count())
        .where(QueryLog.tenant_id == tenant.id)
        .group_by(QueryLog.question)
        .order_by(func.count().desc())
        .limit(10)
    )
    low_confidence = await db.execute(
        select(QueryLog.question, QueryLog.confidence_score)
        .where(QueryLog.tenant_id == tenant.id, QueryLog.confidence_score < 0.4)
        .order_by(QueryLog.created_at.desc())
        .limit(10)
    )
    total_result = await db.execute(
        select(func.count(), func.avg(QueryLog.latency_ms), func.avg(QueryLog.confidence_score))
        .where(QueryLog.tenant_id == tenant.id)
    )
    stats = total_result.one()
    return {
        "top_queries": [{"question": q, "count": c} for q, c in top_queries.all()],
        "low_confidence_queries": [
            {"question": q, "confidence": s} for q, s in low_confidence.all()
        ],
        "total_queries": stats[0] or 0,
        "avg_latency_ms": round(float(stats[1] or 0), 1),
        "avg_confidence": round(float(stats[2] or 0), 3),
    }
