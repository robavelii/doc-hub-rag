import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plan = Column(String, nullable=False, default="free")
    api_key_hash = Column(String, unique=True, nullable=False)
    api_key_prefix = Column(String(8), nullable=False, index=True)
    widget_config = Column(JSONB, nullable=False, default=dict)
    monthly_token_limit = Column(Integer, nullable=False, default=100_000)
    storage_limit_bytes = Column(BigInteger, nullable=False, default=100 * 1024 * 1024)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
