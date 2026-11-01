"""Audit log access/export and data-retention settings (owner/admin)."""

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_owner
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import log_audit

router = APIRouter(tags=["compliance"])

EXPORT_BATCH = 1000
EXPORT_COLUMNS = ["created_at", "action", "user_email", "user_id", "ip_address", "details"]


def _filtered(tenant: Tenant, since: datetime | None, until: datetime | None, action: str | None):
    query = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.tenant_id == tenant.id)
    )
    if since:
        query = query.where(AuditLog.created_at >= since)
    if until:
        query = query.where(AuditLog.created_at < until)
    if action:
        query = query.where(AuditLog.action == action)
    return query


def _row(entry: AuditLog, email: str | None) -> dict:
    return {
        "id": str(entry.id),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "action": entry.action,
        "user_id": str(entry.user_id) if entry.user_id else None,
        "user_email": email,
        "ip_address": entry.ip_address,
        "details": entry.details or {},
    }


@router.get("/audit-logs")
async def list_audit_logs(
    since: datetime | None = None,
    until: datetime | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Newest first. Page with `until=<created_at of the last row>`."""
    rows = await db.execute(_filtered(tenant, since, until, action).order_by(AuditLog.created_at.desc()).limit(limit))
    return [_row(entry, email) for entry, email in rows.all()]


@router.get("/audit-logs/export")
async def export_audit_logs(
    request: Request,
    format: Literal["csv", "jsonl"] = "csv",
    since: datetime | None = None,
    until: datetime | None = None,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Streams the whole (filtered) log, oldest first, for SIEM import or auditors."""
    user = getattr(request.state, "user", None)
    await log_audit(
        db, "audit_log_exported", tenant_id=str(tenant.id), user_id=str(user.id) if user else None,
        details={"format": format, "since": since.isoformat() if since else None, "until": until.isoformat() if until else None},
    )
    base = _filtered(tenant, since, until, None).order_by(AuditLog.created_at, AuditLog.id)

    async def batches() -> AsyncIterator[list[dict]]:
        offset = 0
        while True:
            rows = (await db.execute(base.offset(offset).limit(EXPORT_BATCH))).all()
            if not rows:
                return
            yield [_row(entry, email) for entry, email in rows]
            offset += len(rows)

    async def as_csv() -> AsyncIterator[str]:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        yield buf.getvalue()
        async for batch in batches():
            buf.seek(0)
            buf.truncate()
            for row in batch:
                writer.writerow({**row, "details": json.dumps(row["details"], sort_keys=True)})
            yield buf.getvalue()

    async def as_jsonl() -> AsyncIterator[str]:
        async for batch in batches():
            yield "".join(json.dumps(row, sort_keys=True) + "\n" for row in batch)

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return StreamingResponse(
        as_csv() if format == "csv" else as_jsonl(),
        media_type="text/csv" if format == "csv" else "application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="audit-log-{tenant.slug}-{stamp}.{format}"'},
    )


class RetentionSettings(BaseModel):
    # None keeps data forever.
    content_retention_days: int | None = Field(default=None, ge=1, le=3650)
    audit_retention_days: int | None = Field(default=None, ge=90, le=3650)  # auditors expect >= 90 days


@router.get("/settings/retention")
async def get_retention(tenant: Tenant = Depends(require_owner)):
    return {
        "content_retention_days": tenant.content_retention_days,
        "audit_retention_days": tenant.audit_retention_days,
    }


@router.put("/settings/retention")
async def set_retention(
    body: RetentionSettings, request: Request, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    tenant.content_retention_days = body.content_retention_days
    tenant.audit_retention_days = body.audit_retention_days
    await db.commit()
    user = getattr(request.state, "user", None)
    await log_audit(db, "retention_updated", tenant_id=str(tenant.id), user_id=str(user.id) if user else None,
                    details=body.model_dump())
    return body.model_dump()
