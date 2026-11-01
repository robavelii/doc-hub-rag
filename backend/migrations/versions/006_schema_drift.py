"""align timestamp nullability with models (caught by `alembic check` in CI)

Revision ID: 006
Revises: 005
Create Date: 2026-11-01

"""
from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = [
    ("email_verification_tokens", "created_at"),
    ("password_reset_tokens", "created_at"),
    ("refresh_tokens", "created_at"),
    ("stripe_webhook_events", "processed_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(f"UPDATE {table} SET {column} = now() WHERE {column} IS NULL")
        op.alter_column(table, column, nullable=False)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=True)
