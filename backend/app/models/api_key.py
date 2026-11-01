import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, default="Default")
    key_prefix = Column(String(8), nullable=False, index=True)
    key_hash = Column(String, nullable=False, unique=True)
    # "secret" = full tenant API for server-side use; "publishable" = query-only, safe in a web page.
    kind = Column(String, nullable=False, default="secret", server_default="secret")
    # Publishable keys only: answer from this collection (+ General) instead of all tenant-visible ones.
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), nullable=True)
    last_used_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
