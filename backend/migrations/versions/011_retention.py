"""data retention settings and audit log time index

Revision ID: 011
Revises: 010
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("content_retention_days", sa.Integer(), nullable=True))
    op.add_column("tenants", sa.Column("audit_retention_days", sa.Integer(), nullable=True))
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_column("tenants", "audit_retention_days")
    op.drop_column("tenants", "content_retention_days")
