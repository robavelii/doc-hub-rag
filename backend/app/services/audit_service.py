from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_tenant_rls
from app.models.audit_log import AuditLog


async def log_audit(
    db: AsyncSession,
    action: str,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    if tenant_id:
        await set_tenant_rls(db, tenant_id)
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    await db.commit()
