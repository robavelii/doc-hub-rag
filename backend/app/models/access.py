"""Groups and collections: who can see which documents.

A document lives in at most one collection (NULL = "General", visible to the
whole tenant). A collection is either visible to the whole tenant or
restricted to the groups granted access. Owners/admins and secret API keys
see everything. Groups are managed by hand or synced from the customer's
identity provider over SCIM (`source="scim"`, `external_id` = IdP group id).
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

VISIBILITY_TENANT = "tenant"
VISIBILITY_RESTRICTED = "restricted"


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
        UniqueConstraint("tenant_id", "external_id", name="uq_groups_tenant_external_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False, default="manual", server_default="manual")
    external_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_collections_tenant_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    visibility = Column(String, nullable=False, default=VISIBILITY_TENANT, server_default=VISIBILITY_TENANT)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CollectionAccess(Base):
    __tablename__ = "collection_access"

    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
