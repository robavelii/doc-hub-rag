"""Answering questions: cache → (condense follow-up) → retrieve → prompt → generate → log."""

import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.providers import get_ai_provider
from app.providers.fallback_provider import FallbackProvider
from app.services.cache_service import get_cache, get_corpus_version, set_cache
from app.services.citations import StreamingCitationRewriter, rewrite_citations
from app.services.retrieval import CONTEXT_CHUNK_COUNT, RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 6000
HISTORY_FOR_PROMPT = 10
CACHE_TTL_SECONDS = 3600
# Per-message overhead of the chat format (role, separators); OpenAI documents ~3-4 tokens.
TOKENS_PER_MESSAGE = 4
NO_DOCUMENTS_ANSWER = "I don't have any documents to search. Please upload some documents first."

SYSTEM_PROMPT = """You are a document Q&A assistant. Answer using ONLY the numbered Context passages below.

RULES:
1. Answer the specific question directly and concisely first (a name, number, date, or one short sentence).
2. Add supporting detail only when it helps; do NOT reproduce entire documents or long excerpts.
3. Quote only the minimal line or figure that supports your answer.
4. Cite every fact with the passage number in square brackets, e.g. [1] or [2][3]. Never invent numbers.
5. If the Context has no relevant information, say: "I don't have that information in the current knowledge base."

Context:
{context}
"""

CONDENSE_PROMPT = """Rewrite the user's latest message as one standalone search query that can be
understood without the conversation. Keep names, numbers and technical terms. Return only the query."""

__all__ = [
    "CONTEXT_CHUNK_COUNT",
    "SYSTEM_PROMPT",
    "build_cache_key",
    "complete_rag_query",
    "count_prompt_tokens",
    "run_rag_query",
    "stream_rag_query",
]


# --- cache ---------------------------------------------------------------------

def _normalize_question(question: str) -> str:
    return " ".join(question.lower().split())


async def build_cache_key(tenant_id: str, question: str, history: list[dict] | None) -> str:
    """An answer is reusable only for the same question, the same conversation
    context and the same version of the tenant's documents.

    Phase 2 note: once documents have per-user permissions, the caller's
    permission scope must be part of this key too.
    """
    try:
        corpus_version = await get_corpus_version(tenant_id)
    except Exception as exc:  # cache is an optimisation; never fail a query on it
        logger.warning("corpus version unavailable: %s", exc)
        corpus_version = -1
    recent = (history or [])[-HISTORY_FOR_PROMPT:]
    history_digest = hashlib.sha256(
        json.dumps([[m.get("role"), m.get("content")] for m in recent]).encode()
    ).hexdigest()
    raw = f"{tenant_id}|v{corpus_version}|{history_digest}|{_normalize_question(question)}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _cache_get(key: str) -> str | None:
    try:
        return await get_cache(key)
    except Exception as exc:
        logger.warning("answer cache read failed: %s", exc)
        return None


async def _cache_set(key: str, value: dict) -> None:
    try:
        await set_cache(key, json.dumps(value), ttl=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("answer cache write failed: %s", exc)


# --- query understanding ---------------------------------------------------------

def _has_real_chat_model(provider) -> bool:
    if isinstance(provider, FallbackProvider):
        return any(name != "mock" for name in provider.chat_provider_names)
    return getattr(provider, "provider_name", "mock") != "mock"


async def build_search_query(question: str, history: list[dict] | None) -> str:
    """Turn a follow-up ("what about the second one?") into a self-contained query.

    Uses the chat model when one is configured; otherwise (or on failure) falls
    back to prefixing the previous user message, which still carries the topic.
    With no history the question is used as is, unless ENABLE_QUERY_REWRITE is on.
    """
    previous_user = next((m["content"] for m in reversed(history or []) if m.get("role") == "user"), "")
    if not previous_user and not settings.ENABLE_QUERY_REWRITE:
        return question

    provider = get_ai_provider()
    if _has_real_chat_model(provider):
        transcript = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in (history or [])[-6:])
        try:
            rewritten = await provider.chat_completion(
                [
                    {"role": "system", "content": CONDENSE_PROMPT},
                    {"role": "user", "content": f"Conversation:\n{transcript}\n\nLatest message: {question}"},
                ],
                max_tokens=80,
            )
            rewritten = rewritten.strip().strip('"')
            if rewritten:
                return rewritten
        except Exception as exc:
            logger.warning("query condensing failed, using heuristic: %s", exc)
    return f"{previous_user} {question}".strip()


# --- prompt -----------------------------------------------------------------------

def _passage_header(n: int, chunk: RetrievedChunk) -> str:
    location = [chunk.filename]
    if chunk.metadata.get("heading"):
        location.append(chunk.metadata["heading"])
    if chunk.metadata.get("page"):
        location.append(f"page {chunk.metadata['page']}")
    return f"[{n}] (from {' · '.join(location)}):"


def build_context(chunks: list[RetrievedChunk]) -> tuple[str, list[RetrievedChunk]]:
    parts, used, size = [], [], 0
    for chunk in chunks:
        block = f"{_passage_header(len(used) + 1, chunk)}\n{chunk.text}"
        if size + len(block) > MAX_CONTEXT_CHARS and parts:
            break
        parts.append(block)
        used.append(chunk)
        size += len(block)
    return "\n\n---\n\n".join(parts), used


def _source(n: int, chunk: RetrievedChunk) -> dict:
    return {
        "n": n,
        "id": chunk.id,
        "filename": chunk.filename,
        "text": chunk.text[:200],
        "doc_id": chunk.doc_id,
        "heading": chunk.metadata.get("heading"),
        "page": chunk.metadata.get("page"),
    }


def count_prompt_tokens(provider, messages: list[dict]) -> int:
    return sum(provider.count_tokens(m.get("content") or "") + TOKENS_PER_MESSAGE for m in messages)


async def run_rag_query(
    question: str,
    tenant_id: str,
    db: AsyncSession,
    conversation_history: list[dict] | None = None,
    search_query: str | None = None,
) -> dict:
    """Retrieve context and build the prompt.

    `question` is what the user asked (goes in the prompt); retrieval uses
    `search_query`, or a condensed version of the question when it is a follow-up.
    """
    start = time.time()
    cache_key = await build_cache_key(tenant_id, question, conversation_history)
    cached = await _cache_get(cache_key)
    if cached:
        return {**json.loads(cached), "from_cache": True}

    query = search_query or await build_search_query(question, conversation_history)
    result = await retrieve(db, tenant_id, query, top_k=CONTEXT_CHUNK_COUNT)
    if not result.chunks:
        return {"answer": NO_DOCUMENTS_ANSWER, "sources": [], "confidence": 0.0, "from_cache": False}

    context, used = build_context(result.chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
    if conversation_history:
        messages.extend(conversation_history[-HISTORY_FOR_PROMPT:])
    messages.append({"role": "user", "content": question})

    return {
        "messages": messages,
        "source_ids": [c.id for c in used],
        "citation_map": {n: c.id for n, c in enumerate(used, start=1)},
        "sources": [_source(n, c) for n, c in enumerate(used, start=1)],
        "confidence": result.confidence,
        "search_query": query,
        "cache_key": cache_key,
        "start_time": start,
        "question": question,
    }


# --- generation -------------------------------------------------------------------

def _tier(confidence: float) -> str:
    return "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low"


def _chat_provider_metrics(provider) -> dict:
    if isinstance(provider, FallbackProvider):
        return {"provider": provider.last_chat_provider, "model": provider.last_chat_model}
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
    return {
        "type": "done",
        "sources": context.get("sources", []),
        "confidence": confidence,
        "confidence_tier": _tier(confidence),
        "tokens_total": tokens_total if tokens_total is not None else context.get("tokens_total"),
        "latency_ms": latency_ms if latency_ms is not None else context.get("latency_ms"),
        "from_cache": from_cache or context.get("from_cache", False),
        "provider": provider or context.get("provider"),
        "model": model or context.get("model"),
        "query_log_id": query_log_id or context.get("query_log_id"),
    }


async def _record(context: dict, tenant_id: str, db: AsyncSession, provider, answer: str) -> dict:
    """Persist the query log + usage and cache the answer. Returns the response metrics."""
    from app.models.query_log import QueryLog
    from app.services.usage_service import record_query_usage

    metrics = _chat_provider_metrics(provider)
    latency_ms = int((time.time() - context["start_time"]) * 1000)
    tokens_total = count_prompt_tokens(provider, context["messages"]) + provider.count_tokens(answer)

    log_id = uuid.uuid4()
    db.add(
        QueryLog(
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
    )
    await db.commit()
    await record_query_usage(str(tenant_id), tokens_total, str(log_id), db)
    await _cache_set(
        context["cache_key"],
        {
            "answer": answer,
            "sources": context["sources"],
            "confidence": context["confidence"],
            "tokens_total": tokens_total,
            "latency_ms": latency_ms,
            **metrics,
        },
    )
    return {"tokens_total": tokens_total, "latency_ms": latency_ms, "query_log_id": str(log_id), **metrics}


async def complete_rag_query(context: dict, tenant_id: str, db: AsyncSession) -> dict:
    if "answer" in context:
        return context

    provider = get_ai_provider()
    raw = await provider.chat_completion(context["messages"])
    answer = rewrite_citations(raw, context["citation_map"])
    recorded = await _record(context, tenant_id, db, provider, answer)
    return {
        "answer": answer,
        "sources": context["sources"],
        "confidence": context["confidence"],
        "confidence_tier": _tier(context["confidence"]),
        "from_cache": False,
        **recorded,
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def stream_rag_query(
    question: str,
    tenant_id: str,
    db: AsyncSession,
    conversation_history: list[dict] | None = None,
) -> AsyncIterator[str]:
    stream_start = time.time()
    context = await run_rag_query(question, tenant_id, db, conversation_history)

    if "answer" in context:
        latency_ms = int((time.time() - stream_start) * 1000)
        yield _sse({"type": "chunk", "content": context["answer"]})
        yield _sse(_stream_done_payload(context, latency_ms=latency_ms, from_cache=context.get("from_cache", False)))
        return

    provider = get_ai_provider()
    rewriter = StreamingCitationRewriter(context["citation_map"])
    full_response = ""
    async for delta in provider.chat_completion_stream(context["messages"]):
        out = rewriter.feed(delta)
        if out:
            full_response += out
            yield _sse({"type": "chunk", "content": out})
    tail = rewriter.flush()
    if tail:
        full_response += tail
        yield _sse({"type": "chunk", "content": tail})

    recorded = await _record(context, tenant_id, db, provider, full_response)
    yield _sse(_stream_done_payload(context, **recorded))
