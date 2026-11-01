"""hybrid search: HNSW vector index, full-text search column, chunk metadata

Revision ID: 008
Revises: 007
Create Date: 2026-11-01

- IVFFlat was created on an empty table, so its centroids were meaningless and
  recall degraded as data arrived. HNSW needs no training and stays accurate.
- `search_vector` is a generated tsvector with a GIN index, replacing
  unindexed ILIKE scans for keyword retrieval.
- `metadata` holds structural context (heading path, page number).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "ALTER TABLE chunks ADD COLUMN search_vector tsvector GENERATED ALWAYS AS "
        "(to_tsvector('english', coalesce(filename, '') || ' ' || coalesce(text, ''))) STORED"
    )
    op.execute("CREATE INDEX ix_chunks_search_vector ON chunks USING gin (search_vector)")
    op.execute("ALTER TABLE chunks ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP COLUMN metadata")
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_vector")
    op.execute("ALTER TABLE chunks DROP COLUMN search_vector")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
