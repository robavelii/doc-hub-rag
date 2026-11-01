"""enterprise SSO: claimed email domains and SSO enforcement

Revision ID: 010
Revises: 009
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("sso_enforced", sa.Boolean(), nullable=False, server_default="false"))
    op.create_table(
        "sso_domains",
        sa.Column("domain", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sso_domains_tenant_id", "sso_domains", ["tenant_id"])
    # Discovery is a cross-tenant lookup done with the privileged role only.
    op.execute("REVOKE ALL ON sso_domains FROM app_user")


def downgrade() -> None:
    op.drop_table("sso_domains")
    op.drop_column("tenants", "sso_enforced")
