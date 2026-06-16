import uuid
from typing import Any, Dict, List

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk


def _format_vector(embedding: List[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _row_to_candidate(row, tenant_id: str, score: float) -> Dict[str, Any]:
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


async def upsert_chunks(
    session: AsyncSession,
    tenant_id: str,
    document_id: str,
    chunks: List[Dict[str, Any]],
) -> None:
    for item in chunks:
        chunk = Chunk(
            id=uuid.UUID(item["id"]) if isinstance(item["id"], str) else item["id"],
            tenant_id=uuid.UUID(tenant_id),
            document_id=uuid.UUID(document_id),
            chunk_index=item["chunk_index"],
            text=item["text"],
            text_preview=item.get("text_preview", item["text"][:500]),
            filename=item.get("filename", ""),
            embedding=item["embedding"],
        )
        session.add(chunk)
    await session.commit()


def upsert_chunks_sync(session, tenant_id: str, document_id: str, chunks: List[Dict[str, Any]]) -> None:
    for item in chunks:
        chunk = Chunk(
            id=uuid.UUID(item["id"]) if isinstance(item["id"], str) else item["id"],
            tenant_id=uuid.UUID(tenant_id),
            document_id=uuid.UUID(document_id),
            chunk_index=item["chunk_index"],
            text=item["text"],
            text_preview=item.get("text_preview", item["text"][:500]),
            filename=item.get("filename", ""),
            embedding=item["embedding"],
        )
        session.add(chunk)
    session.commit()


async def search_vectors(
    session: AsyncSession,
    tenant_id: str,
    embedding: List[float],
    top_k: int = 40,
) -> List[Dict[str, Any]]:
    query = text(
        """
        SELECT id, document_id, chunk_index, text, text_preview, filename,
               1 - (embedding <=> CAST(:embedding AS vector)) AS score
        FROM chunks
        WHERE tenant_id = CAST(:tenant_id AS uuid)
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    result = await session.execute(
        query,
        {
            "embedding": _format_vector(embedding),
            "tenant_id": tenant_id,
            "top_k": top_k,
        },
    )
    return [_row_to_candidate(row, tenant_id, float(row.score)) for row in result.fetchall()]


async def search_chunks_by_keywords(
    session: AsyncSession,
    tenant_id: str,
    terms: List[str],
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    if not terms:
        return []

    conditions = []
    params: dict[str, Any] = {"tenant_id": tenant_id, "top_k": top_k}
    for index, term in enumerate(terms[:8]):
        key = f"term{index}"
        conditions.append(f"text ILIKE :{key}")
        params[key] = f"%{term}%"

    where_clause = " OR ".join(conditions)
    query = text(
        f"""
        SELECT id, document_id, chunk_index, text, text_preview, filename
        FROM chunks
        WHERE tenant_id = CAST(:tenant_id AS uuid)
          AND ({where_clause})
        LIMIT :top_k
        """
    )
    result = await session.execute(query, params)
    return [_row_to_candidate(row, tenant_id, 0.55) for row in result.fetchall()]


def search_vectors_sync(session, tenant_id: str, embedding: List[float], top_k: int = 40) -> List[Dict[str, Any]]:
    query = text(
        """
        SELECT id, document_id, chunk_index, text, text_preview, filename,
               1 - (embedding <=> CAST(:embedding AS vector)) AS score
        FROM chunks
        WHERE tenant_id = CAST(:tenant_id AS uuid)
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    result = session.execute(
        query,
        {
            "embedding": _format_vector(embedding),
            "tenant_id": tenant_id,
            "top_k": top_k,
        },
    )
    return [_row_to_candidate(row, tenant_id, float(row.score)) for row in result.fetchall()]


async def delete_doc_vectors(session: AsyncSession, document_id: str, tenant_id: str) -> None:
    await session.execute(
        delete(Chunk).where(Chunk.document_id == uuid.UUID(document_id), Chunk.tenant_id == uuid.UUID(tenant_id))
    )
    await session.commit()


def delete_doc_vectors_sync(session, document_id: str, tenant_id: str) -> None:
    session.execute(
        delete(Chunk).where(Chunk.document_id == uuid.UUID(document_id), Chunk.tenant_id == uuid.UUID(tenant_id))
    )
    session.commit()
