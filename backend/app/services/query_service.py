import hashlib
import json
import re
import time
import uuid
from typing import AsyncIterator, List, Optional

from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers import get_ai_provider
from app.providers.fallback_provider import FallbackProvider
from app.services.cache_service import get_cache, set_cache
from app.services.embedding_service import embed_single
from app.services.vector_service import search_chunks_by_keywords, search_vectors

VECTOR_TOP_K = 40
KEYWORD_TOP_K = 20
CONTEXT_CHUNK_COUNT = 6
MAX_CONTEXT_CHARS = 6000

SYSTEM_PROMPT = """You are a document Q&A assistant. Answer using ONLY the Context below.

RULES:
1. Answer the specific question directly and concisely first (a name, number, date, or one short sentence).
2. Add supporting detail only when it helps; do NOT reproduce entire documents or long excerpts.
3. Quote only the minimal line or figure that supports your answer.
4. Cite every fact with [source:CHUNK_ID] using the exact chunk IDs from Context.
5. If Context has no relevant information, say: "I don't have that information in the current knowledge base."

Context:
{context}
"""

_QUERY_STOPWORDS = frozenset(
    {
        "what", "when", "where", "which", "who", "whom", "whose", "how", "why",
        "is", "are", "was", "were", "the", "a", "an", "do", "does", "did",
        "can", "could", "would", "should", "tell", "about", "me", "my",
        "and", "for", "non", "any", "all", "this", "that", "with", "from",
        "persons", "person",
    }
)

_QUERY_SYNONYMS: dict[str, list[str]] = {
    "balance": ["running balance", "usd balance", "account balance"],
    "net": ["net earnings", "net balance"],
    "name": ["account holder", "subject"],
    "holder": ["account holder"],
    "account": ["payoneer account"],
    "earnings": ["net earnings"],
    "salary": ["earnings", "net earnings"],
}


def _query_terms(question: str) -> list[str]:
    terms: list[str] = []
    lower = question.lower()

    for phrase in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", lower):
        if len(phrase) > 2 and phrase not in _QUERY_STOPWORDS:
            terms.append(phrase)

    for word in re.findall(r"[a-z0-9']+", lower):
        cleaned = re.sub(r"'s$", "", word.strip("'"))
        if len(cleaned) > 2 and cleaned not in _QUERY_STOPWORDS and cleaned not in terms:
            terms.append(cleaned)

    return terms


def _expand_search_terms(terms: list[str]) -> list[str]:
    expanded = list(terms)
    for term in terms:
        for alias in _QUERY_SYNONYMS.get(term, []):
            if alias not in expanded:
                expanded.append(alias)
    return expanded[:12]


def _merge_candidates(vector_results: list, keyword_results: list) -> list:
    merged: dict[str, dict] = {}
    for candidate in vector_results:
        merged[candidate["id"]] = candidate
    for candidate in keyword_results:
        existing = merged.get(candidate["id"])
        if existing:
            existing["score"] = max(existing["score"], candidate["score"])
        else:
            merged[candidate["id"]] = candidate
    return list(merged.values())


def _uses_mock_scoring() -> bool:
    return (
        settings.embedding_provider_name == "mock"
        or (settings.embedding_provider_name == "openai" and not settings.OPENAI_API_KEY)
    )


def _compute_confidence(top_chunks: list, use_mock_scoring: bool) -> float:
    if not top_chunks:
        return 0.0

    vector_scores = [max(0.0, min(1.0, c["score"])) for c, _ in top_chunks[:4]]
    combined_scores = [score for _, score in top_chunks[:4]]

    if use_mock_scoring:
        keyword_component = sum(combined_scores[:3]) / min(3, len(combined_scores))
        confidence = 0.35 * (sum(vector_scores) / len(vector_scores)) + 0.65 * keyword_component
    else:
        strong_vectors = [s for s in vector_scores if s >= 0.45]
        if strong_vectors:
            confidence = sum(strong_vectors) / len(strong_vectors)
        elif vector_scores:
            confidence = max(vector_scores) * 0.55
        else:
            confidence = combined_scores[0] * 0.4 if combined_scores else 0.0

    return round(min(0.92, max(0.0, confidence)), 3)


def _rank_chunks(question: str, candidates: list) -> tuple[list, float]:
    texts = [c["metadata"]["text"] for c in candidates]
    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    raw_bm25 = bm25.get_scores(question.lower().split())
    max_bm = max(raw_bm25) if len(raw_bm25) else 0.0
    min_bm = min(raw_bm25) if len(raw_bm25) else 0.0
    bm_range = max_bm - min_bm or 1.0
    norm_bm25 = [(score - min_bm) / bm_range for score in raw_bm25]

    query_terms = _query_terms(question)
    use_mock_scoring = _uses_mock_scoring()

    combined = []
    for candidate, norm_bm, _raw_bm in zip(candidates, norm_bm25, raw_bm25):
        text_lower = candidate["metadata"]["text"].lower()
        keyword_score = (
            sum(1 for term in query_terms if term in text_lower) / max(len(query_terms), 1)
            if query_terms
            else 0.5
        )
        vector_score = max(0.0, min(1.0, candidate["score"]))
        if use_mock_scoring:
            score = 0.1 * vector_score + 0.3 * norm_bm + 0.6 * keyword_score
        else:
            score = 0.65 * vector_score + 0.25 * norm_bm + 0.1 * keyword_score
        combined.append((candidate, min(1.0, score)))

    combined.sort(key=lambda item: item[1], reverse=True)
    top_chunks = combined[:CONTEXT_CHUNK_COUNT]
    confidence = _compute_confidence(top_chunks, use_mock_scoring)
    return top_chunks, confidence


def _chat_provider_metrics(provider) -> dict:
    if isinstance(provider, FallbackProvider):
        return {
            "provider": provider.last_chat_provider,
            "model": provider.last_chat_model,
        }
    return {
        "provider": getattr(provider, "provider_name", provider.__class__.__name__),
        "model": getattr(provider, "chat_model_name", "unknown"),
    }


def _stream_done_payload(
    context: dict,
    *,
    tokens_total: int | None = None,
    latency_ms: int | None = None,
    from_cache: bool = False,
    provider: str | None = None,
    model: str | None = None,
    query_log_id: str | None = None,
) -> dict:
    confidence = context.get("confidence", 0.0)
    tier = "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low"
    return {
        "type": "done",
        "sources": context.get("sources", []),
        "confidence": confidence,
        "confidence_tier": tier,
        "tokens_total": tokens_total if tokens_total is not None else context.get("tokens_total"),
        "latency_ms": latency_ms if latency_ms is not None else context.get("latency_ms"),
        "from_cache": from_cache or context.get("from_cache", False),
        "provider": provider or context.get("provider"),
        "model": model or context.get("model"),
        "query_log_id": query_log_id or context.get("query_log_id"),
    }


async def run_rag_query(
    question: str,
    tenant_id: str,
    db: AsyncSession,
    conversation_history: Optional[List[dict]] = None,
) -> dict:
    start = time.time()
    cache_key = hashlib.sha256(f"{tenant_id}:{question}".encode()).hexdigest()
    cached = await get_cache(cache_key)
    if cached:
        return {**json.loads(cached), "from_cache": True}

    query_terms = _query_terms(question)
    search_terms = _expand_search_terms(query_terms)

    query_embedding = await embed_single(question)
    vector_candidates = await search_vectors(db, tenant_id, query_embedding, top_k=VECTOR_TOP_K)
    keyword_candidates = await search_chunks_by_keywords(db, tenant_id, search_terms, top_k=KEYWORD_TOP_K)
    candidates = _merge_candidates(vector_candidates, keyword_candidates)

    if not candidates:
        return {
            "answer": "I don't have any documents to search. Please upload some documents first.",
            "sources": [],
            "confidence": 0.0,
            "from_cache": False,
        }

    top_chunks, confidence = _rank_chunks(question, candidates)

    context_parts = []
    source_ids = []
    context_size = 0
    for chunk, _ in top_chunks:
        chunk_id = chunk["id"]
        text = chunk["metadata"]["text"]
        filename = chunk["metadata"].get("filename", "document")
        block = f"[{chunk_id}] (from {filename}):\n{text}"
        if context_size + len(block) > MAX_CONTEXT_CHARS and context_parts:
            break
        context_parts.append(block)
        source_ids.append(chunk_id)
        context_size += len(block)

    context = "\n\n---\n\n".join(context_parts)
    ranked_for_response = [(c, s) for c, s in top_chunks if c["id"] in source_ids]

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
    if conversation_history:
        messages.extend(conversation_history[-10:])
    messages.append({"role": "user", "content": question})

    return {
        "messages": messages,
        "source_ids": source_ids,
        "sources": [
            {
                "id": c["id"],
                "filename": c["metadata"].get("filename"),
                "text": c["metadata"]["text"][:200],
                "doc_id": c["metadata"].get("doc_id"),
            }
            for c, _ in ranked_for_response
        ],
        "confidence": round(confidence, 3),
        "cache_key": cache_key,
        "start_time": start,
        "question": question,
    }


async def complete_rag_query(context: dict, tenant_id: str, db: AsyncSession) -> dict:
    if "answer" in context:
        return context

    provider = get_ai_provider()
    answer = await provider.chat_completion(context["messages"])
    metrics = _chat_provider_metrics(provider)
    latency_ms = int((time.time() - context["start_time"]) * 1000)
    tokens_total = provider.count_tokens(context["question"]) + provider.count_tokens(answer)

    from app.models.query_log import QueryLog
    from app.services.usage_service import record_query_usage

    log_id = uuid.uuid4()
    log = QueryLog(
        id=log_id,
        tenant_id=tenant_id,
        question=context["question"],
        answer=answer,
        source_chunk_ids=[uuid.UUID(s) for s in context["source_ids"]],
        tokens_total=tokens_total,
        latency_ms=latency_ms,
        confidence_score=context["confidence"],
        from_cache=False,
    )
    db.add(log)
    await db.commit()
    await record_query_usage(str(tenant_id), tokens_total, str(log_id), db)

    confidence = context["confidence"]
    tier = "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low"
    result = {
        "answer": answer,
        "sources": context["sources"],
        "confidence": confidence,
        "confidence_tier": tier,
        "from_cache": False,
        "tokens_total": tokens_total,
        "latency_ms": latency_ms,
        "query_log_id": str(log_id),
        **metrics,
    }
    await set_cache(
        context["cache_key"],
        json.dumps(
            {
                "answer": answer,
                "sources": context["sources"],
                "confidence": context["confidence"],
                "tokens_total": tokens_total,
                "latency_ms": latency_ms,
                **metrics,
            }
        ),
        ttl=3600,
    )
    return result


async def _maybe_rewrite_query(question: str) -> str:
    if not settings.ENABLE_QUERY_REWRITE:
        return question
    provider = get_ai_provider()
    try:
        rewritten = await provider.chat_completion([
            {"role": "system", "content": "Rewrite the user question for better document search. Return only the rewritten question."},
            {"role": "user", "content": question},
        ])
        return rewritten.strip() or question
    except Exception:
        return question


async def stream_rag_query(
    question: str,
    tenant_id: str,
    db: AsyncSession,
    conversation_history: Optional[List[dict]] = None,
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    stream_start = time.time()
    search_question = await _maybe_rewrite_query(question)
    context = await run_rag_query(search_question, tenant_id, db, conversation_history)
    context["question"] = question

    if "answer" in context:
        latency_ms = int((time.time() - stream_start) * 1000)
        yield f"data: {json.dumps({'type': 'chunk', 'content': context['answer']})}\n\n"
        yield f"data: {json.dumps(_stream_done_payload(context, latency_ms=latency_ms, from_cache=context.get('from_cache', False)))}\n\n"
        return

    provider = get_ai_provider()
    full_response = ""
    async for delta in provider.chat_completion_stream(context["messages"]):
        full_response += delta
        yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"

    metrics = _chat_provider_metrics(provider)
    latency_ms = int((time.time() - context["start_time"]) * 1000)
    tokens_total = provider.count_tokens(context["question"]) + provider.count_tokens(full_response)

    from app.models.query_log import QueryLog
    from app.services.usage_service import record_query_usage

    log_id = uuid.uuid4()
    log = QueryLog(
        id=log_id,
        tenant_id=tenant_id,
        question=context["question"],
        answer=full_response,
        source_chunk_ids=[uuid.UUID(s) for s in context["source_ids"]],
        tokens_total=tokens_total,
        latency_ms=latency_ms,
        confidence_score=context["confidence"],
        from_cache=False,
    )
    db.add(log)
    await db.commit()
    await record_query_usage(str(tenant_id), tokens_total, str(log_id), db)

    cache_data = {
        "answer": full_response,
        "sources": context["sources"],
        "confidence": context["confidence"],
        "tokens_total": tokens_total,
        "latency_ms": latency_ms,
        "from_cache": False,
        **metrics,
    }
    await set_cache(context["cache_key"], json.dumps(cache_data), ttl=3600)

    yield f"data: {json.dumps(_stream_done_payload(context, tokens_total=tokens_total, latency_ms=latency_ms, query_log_id=str(log_id), **metrics))}\n\n"
