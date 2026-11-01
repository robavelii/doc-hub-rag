import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SsoDomain(Base):
    """Email domain → tenant for SSO discovery. A domain belongs to at most one tenant.

    Not tenant-scoped by RLS: discovery runs before we know the tenant, through the
    privileged session only.
    """

    __tablename__ = "sso_domains"

    domain = Column(String, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @staticmethod
    def new(domain: str, tenant_id: uuid.UUID) -> "SsoDomain":
        return SsoDomain(domain=domain.lower().strip(), tenant_id=tenant_id)
