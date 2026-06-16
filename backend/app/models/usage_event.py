import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    tokens = Column(Integer, nullable=False, default=0)
    storage_delta_bytes = Column(BigInteger, nullable=False, default=0)
    ref_id = Column(UUID(as_uuid=True))
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
