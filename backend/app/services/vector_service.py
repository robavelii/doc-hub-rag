import re
import uuid
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _row_to_candidate(row, tenant_id: str, score: float) -> dict[str, Any]:
    full_text = row.text or row.text_preview or ""
    return {
        "id": str(row.id),
        "score": score,
        "metadata": {
            "tenant_id": tenant_id,
            "doc_id": str(row.document_id),
            "chunk_index": row.chunk_index,
            "text": full_text,
            "filename": row.filename,
        },
    }


def replace_doc_chunks_sync(
    session, tenant_id: str, document_id: str, chunks: list[dict[str, Any]], collection_id=None
) -> None:
    """Swap a document's chunks in the caller's transaction (no commit).

    Old chunks stay queryable until the caller commits, so re-indexing never
    leaves a document with zero chunks and a failure leaves the old ones intact.
    """
    session.execute(
        delete(Chunk).where(Chunk.document_id == uuid.UUID(document_id), Chunk.tenant_id == uuid.UUID(tenant_id))
    )
    for item in chunks:
        session.add(
            Chunk(
                id=uuid.UUID(item["id"]) if isinstance(item["id"], str) else item["id"],
                tenant_id=uuid.UUID(tenant_id),
                document_id=uuid.UUID(document_id),
                chunk_index=item["chunk_index"],
                text=item["text"],
                text_preview=item.get("text_preview", item["text"][:500]),
                filename=item.get("filename", ""),
                embedding=item["embedding"],
                metadata_=item.get("metadata") or {},
                collection_id=collection_id,
            )
        )


async def delete_doc_vectors(session: AsyncSession, document_id: str, tenant_id: str) -> None:
    await session.execute(
        delete(Chunk).where(Chunk.document_id == uuid.UUID(document_id), Chunk.tenant_id == uuid.UUID(tenant_id))
    )
    await session.commit()


# --- Hybrid search (Phase 1) ---------------------------------------------------

_CHUNK_COLUMNS = "id, document_id, chunk_index, text, text_preview, filename, metadata"
_pgvector_iterative_scan: bool | None = None


async def _supports_iterative_scan(session: AsyncSession) -> bool:
    """pgvector >= 0.8 can keep scanning HNSW until enough rows pass the tenant filter."""
    global _pgvector_iterative_scan
    if _pgvector_iterative_scan is None:
        version = (
            await session.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        ).scalar() or "0"
        major, minor = (int(p) for p in (version.split(".") + ["0"])[:2])
        _pgvector_iterative_scan = (major, minor) >= (0, 8)
    return _pgvector_iterative_scan


def _hybrid_row(row, score: float) -> dict[str, Any]:
    candidate = _row_to_candidate(row, "", score)
    candidate["metadata"]["extra"] = dict(row.metadata or {})
    return candidate


async def vector_search(
    session: AsyncSession, tenant_id: str, embedding: list[float], top_k: int = 40, scope=None
) -> list[dict[str, Any]]:
    """Nearest chunks by cosine similarity, restricted to one tenant.

    A plain `WHERE tenant_id = ... ORDER BY embedding <=> q LIMIT k` over an HNSW
    index filters *after* the index returns its candidates, so small tenants in a
    large table can get few or no results. With pgvector >= 0.8 we enable
    iterative scans; otherwise we search the tenant's rows exactly.
    """
    scope_sql, scope_params = scope.sql_filter() if scope is not None else ("TRUE", {})
    params = {"embedding": _format_vector(embedding), "tenant_id": tenant_id, "top_k": top_k, **scope_params}
    if await _supports_iterative_scan(session):
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        await session.execute(text("SET LOCAL hnsw.ef_search = 100"))
        sql = f"""
            SELECT * FROM (
                SELECT {_CHUNK_COLUMNS}, embedding <=> CAST(:embedding AS vector) AS distance
                FROM chunks
                WHERE tenant_id = CAST(:tenant_id AS uuid) AND {scope_sql}
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            ) hits ORDER BY distance
        """  # noqa: S608 - column list is a constant
    else:
        sql = f"""
            WITH tenant_chunks AS MATERIALIZED (
                SELECT {_CHUNK_COLUMNS}, embedding FROM chunks
                WHERE tenant_id = CAST(:tenant_id AS uuid) AND {scope_sql}
            )
            SELECT {_CHUNK_COLUMNS}, embedding <=> CAST(:embedding AS vector) AS distance
            FROM tenant_chunks
            ORDER BY distance
            LIMIT :top_k
        """  # noqa: S608 - column list is a constant
    rows = (await session.execute(text(sql), params)).fetchall()
    return [_hybrid_row(row, 1.0 - float(row.distance)) for row in rows]


_TSQUERY_TOKEN = re.compile(r"[a-z0-9]+")


def build_or_tsquery(query: str) -> str:
    """Any-term match; ranking (ts_rank_cd) rewards chunks that match more terms.

    Tokens are restricted to [a-z0-9], so the string is safe to pass to to_tsquery.
    English stop words are dropped by Postgres itself.
    """
    tokens = []
    for token in _TSQUERY_TOKEN.findall(query.lower()):
        if len(token) > 1 and token not in tokens:
            tokens.append(token)
    return " | ".join(tokens[:32])


async def fulltext_search(
    session: AsyncSession, tenant_id: str, query: str, top_k: int = 40, scope=None
) -> list[dict[str, Any]]:
    tsquery = build_or_tsquery(query)
    if not tsquery:
        return []
    scope_sql, scope_params = scope.sql_filter() if scope is not None else ("TRUE", {})
    sql = f"""
        SELECT {_CHUNK_COLUMNS}, ts_rank_cd(search_vector, q, 32) AS rank
        FROM chunks, to_tsquery('english', :tsquery) q
        WHERE tenant_id = CAST(:tenant_id AS uuid) AND search_vector @@ q AND {scope_sql}
        ORDER BY rank DESC
        LIMIT :top_k
    """  # noqa: S608 - column list is a constant
    params = {"tsquery": tsquery, "tenant_id": tenant_id, "top_k": top_k, **scope_params}
    rows = (await session.execute(text(sql), params)).fetchall()
    return [_hybrid_row(row, float(row.rank)) for row in rows]
