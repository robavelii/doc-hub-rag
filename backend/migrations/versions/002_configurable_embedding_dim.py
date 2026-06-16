"""configurable embedding dimension

Revision ID: 002
Revises: 001
Create Date: 2026-06-05

Alters chunks.embedding to match EMBEDDING_DIMENSIONS from environment.
Run only when switching embedding providers (e.g. OpenAI 1536 -> Ollama 768).
Re-embed all documents after applying.
"""
import os
import sys
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_DIM = 1536


def _target_dim() -> int:
    backend_root = Path(__file__).resolve().parents[2]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    try:
        from app.config import settings

        return int(settings.EMBEDDING_DIMENSIONS)
    except Exception:
        return int(os.getenv("EMBEDDING_DIMENSIONS", str(_DEFAULT_DIM)))


def upgrade() -> None:
    dim = _target_dim()
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding")
    # Existing vectors may use a different dimension — clear before altering column type.
    op.execute("UPDATE chunks SET embedding = NULL")
    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({dim})")
    op.execute(
        f"""
        CREATE INDEX ix_chunks_embedding ON chunks
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding")
    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({_DEFAULT_DIM})")
    op.execute(
        f"""
        CREATE INDEX ix_chunks_embedding ON chunks
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )
