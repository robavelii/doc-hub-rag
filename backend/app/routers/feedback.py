from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models.feedback import QueryFeedback
from app.models.query_log import QueryLog
from app.models.tenant import Tenant

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    query_log_id: str
    rating: int
    comment: str | None = None


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    if body.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 (up) or -1 (down)")

    log = await db.get(QueryLog, body.query_log_id)
    if not log or str(log.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Query log not found")

    existing = await db.execute(
        select(QueryFeedback).where(QueryFeedback.query_log_id == log.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Feedback already submitted for this query")

    feedback = QueryFeedback(
        query_log_id=log.id,
        tenant_id=tenant.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    await db.commit()
    return {"ok": True}


@router.get("/summary")
async def feedback_summary(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QueryFeedback.rating, func.count())
        .where(QueryFeedback.tenant_id == tenant.id)
        .group_by(QueryFeedback.rating)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {
        "thumbs_up": counts.get(1, 0),
        "thumbs_down": counts.get(-1, 0),
        "total": sum(counts.values()),
    }
