"""Retrieval: find the chunks most likely to answer a query.

Pipeline (measured by evals/run_eval.py):
1. Candidate generation, in parallel conceptually:
   - vector search (HNSW, cosine) on the query embedding
   - full-text search (Postgres tsvector, any-term, ts_rank_cd)
2. Reciprocal rank fusion. Ranks are comparable across both lists, while raw
   scores (cosine vs ts_rank) are not, so no hand-tuned weights are needed.
3. Optional cross-encoder rerank of the top fused candidates.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers import get_ai_provider
from app.services.reranker import relevance_probability, rerank_scores
from app.services.vector_service import fulltext_search, vector_search

logger = logging.getLogger(__name__)

CONTEXT_CHUNK_COUNT = 6
CANDIDATES_PER_RETRIEVER = 40
RRF_K = 60  # standard constant from Cormack et al.; dampens the head of each list


@dataclass
class RetrievedChunk:
    id: str
    doc_id: str
    filename: str
    text: str
    chunk_index: int
    score: float
    metadata: dict = field(default_factory=dict)
    vector_similarity: float | None = None


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    confidence: float
    debug: dict = field(default_factory=dict)


def _to_chunk(candidate: dict) -> RetrievedChunk:
    meta = candidate["metadata"]
    return RetrievedChunk(
        id=candidate["id"],
        doc_id=meta.get("doc_id", ""),
        filename=meta.get("filename") or "document",
        text=meta["text"],
        chunk_index=meta.get("chunk_index", 0),
        score=0.0,
        metadata=meta.get("extra") or {},
    )


def reciprocal_rank_fusion(*ranked_lists: list[dict], k: int = RRF_K) -> list[tuple[dict, float]]:
    scores: dict[str, float] = {}
    first_seen: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, candidate in enumerate(ranked, start=1):
            cid = candidate["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(cid, candidate)
    return sorted(((first_seen[cid], s) for cid, s in scores.items()), key=lambda item: item[1], reverse=True)


def _rerank_text(chunk: RetrievedChunk) -> str:
    heading = chunk.metadata.get("heading")
    return f"{heading}\n{chunk.text}" if heading else chunk.text


async def retrieve(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    *,
    top_k: int = CONTEXT_CHUNK_COUNT,
) -> RetrievalResult:
    vector_hits: list[dict] = []
    try:
        embedding = await get_ai_provider().embed_query(query)
        vector_hits = await vector_search(db, tenant_id, embedding, top_k=CANDIDATES_PER_RETRIEVER)
    except Exception as exc:
        # Full-text search still answers many questions; better than failing the request.
        logger.warning("vector search unavailable, using full-text search only: %s", exc)
    text_hits = await fulltext_search(db, tenant_id, query, top_k=CANDIDATES_PER_RETRIEVER)

    fused = reciprocal_rank_fusion(vector_hits, text_hits)
    if not fused:
        return RetrievalResult(chunks=[], confidence=0.0)

    similarity = {c["id"]: c["score"] for c in vector_hits}
    chunks = []
    for candidate, fused_score in fused[: max(settings.RERANK_POOL, top_k)]:
        chunk = _to_chunk(candidate)
        chunk.score = fused_score
        chunk.vector_similarity = similarity.get(chunk.id)
        chunks.append(chunk)

    scores = await rerank_scores(query, [_rerank_text(c) for c in chunks])
    if scores is not None:
        for chunk, score in zip(chunks, scores, strict=True):
            chunk.score = score
        chunks.sort(key=lambda c: c.score, reverse=True)
        confidence = relevance_probability(chunks[0].score)
    else:
        top_similarity = max((c.vector_similarity or 0.0) for c in chunks[:top_k])
        confidence = max(0.0, min(1.0, top_similarity))

    return RetrievalResult(
        chunks=chunks[:top_k],
        confidence=round(confidence, 3),
        debug={"vector_hits": len(vector_hits), "text_hits": len(text_hits), "reranked": scores is not None},
    )
