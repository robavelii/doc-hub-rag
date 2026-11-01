"""api key kinds (secret/publishable) and per-user conversation ownership

Revision ID: 007
Revises: 006
Create Date: 2026-11-01

Existing conversations have no recorded owner. They are assigned to the
tenant's owner user (the only safe default: previously every member could
read them, and the owner could already see all of them).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("kind", sa.String(), nullable=False, server_default="secret"),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.execute(
        """
        UPDATE conversations c
        SET user_id = (
            SELECT u.id FROM users u
            WHERE u.tenant_id = c.tenant_id AND u.role = 'owner'
            ORDER BY u.created_at
            LIMIT 1
        )
        WHERE c.user_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_column("conversations", "user_id")
    op.drop_column("api_keys", "kind")
