"""Nightly purge of data past each tenant's retention period.

content_retention_days: query logs (and their feedback), conversations (and messages)
audit_retention_days:   audit log entries
Documents, chunks and usage/billing records are never purged here.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.database import AdminSyncSession
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.query_log import QueryLog
from app.models.tenant import Tenant
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task
def purge_expired_data() -> dict:
    now = datetime.now(UTC)
    totals = {"query_logs": 0, "conversations": 0, "audit_logs": 0}
    with AdminSyncSession() as db:
        tenants = db.execute(
            select(Tenant.id, Tenant.content_retention_days, Tenant.audit_retention_days).where(
                (Tenant.content_retention_days.is_not(None)) | (Tenant.audit_retention_days.is_not(None))
            )
        ).all()
        for tenant_id, content_days, audit_days in tenants:
            if content_days:
                cutoff = now - timedelta(days=content_days)
                totals["query_logs"] += db.execute(
                    delete(QueryLog).where(QueryLog.tenant_id == tenant_id, QueryLog.created_at < cutoff)
                ).rowcount
                totals["conversations"] += db.execute(
                    delete(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.updated_at < cutoff)
                ).rowcount
            if audit_days:
                cutoff = now - timedelta(days=audit_days)
                totals["audit_logs"] += db.execute(
                    delete(AuditLog).where(AuditLog.tenant_id == tenant_id, AuditLog.created_at < cutoff)
                ).rowcount
            db.commit()
    logger.info("retention purge: %s", totals)
    return totals
