"""groups, collections and collection-scoped documents/chunks/widget keys

Revision ID: 009
Revises: 008
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NEW_TABLES = ("groups", "group_members", "collections", "collection_access")


def _tenant_fk():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", UUID, primary_key=True),
        _tenant_fk(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_groups_tenant_external_id"),
    )
    op.create_index("ix_groups_tenant_id", "groups", ["tenant_id"])

    op.create_table(
        "group_members",
        sa.Column("group_id", UUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        _tenant_fk(),
    )
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])
    op.create_index("ix_group_members_tenant_id", "group_members", ["tenant_id"])

    op.create_table(
        "collections",
        sa.Column("id", UUID, primary_key=True),
        _tenant_fk(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="tenant"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_collections_tenant_name"),
    )
    op.create_index("ix_collections_tenant_id", "collections", ["tenant_id"])

    op.create_table(
        "collection_access",
        sa.Column("collection_id", UUID, sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", UUID, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        _tenant_fk(),
    )
    op.create_index("ix_collection_access_group_id", "collection_access", ["group_id"])
    op.create_index("ix_collection_access_tenant_id", "collection_access", ["tenant_id"])

    for table in ("documents", "chunks"):
        op.add_column(
            table,
            sa.Column("collection_id", UUID, sa.ForeignKey("collections.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index(f"ix_{table}_collection_id", table, ["collection_id"])
    op.add_column(
        "api_keys",
        sa.Column("collection_id", UUID, sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=True),
    )

    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")


def downgrade() -> None:
    op.drop_column("api_keys", "collection_id")
    for table in ("chunks", "documents"):
        op.drop_index(f"ix_{table}_collection_id", table_name=table)
        op.drop_column(table, "collection_id")
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
