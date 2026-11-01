"""Second-stage reranking of retrieved chunks with a cross-encoder.

A cross-encoder reads the query and each chunk together, so it judges relevance
far better than comparing two independently computed embeddings. It is only
applied to the top fused candidates, which keeps it cheap.

RERANKER=local  in-process MiniLM cross-encoder (fastembed/ONNX, ~80 MB, CPU)
RERANKER=none   keep the fused order
"""

import asyncio
import logging
import math
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _cross_encoder(name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(name, cache_dir=settings.LOCAL_MODEL_CACHE_DIR or None)


def reranker_enabled() -> bool:
    return settings.RERANKER.strip().lower() == "local"


def _score_sync(query: str, documents: list[str]) -> list[float]:
    return [float(s) for s in _cross_encoder(settings.LOCAL_RERANK_MODEL).rerank(query, documents)]


async def rerank_scores(query: str, documents: list[str]) -> list[float] | None:
    """Relevance logits aligned with `documents`, or None when disabled/unavailable."""
    if not documents or not reranker_enabled():
        return None
    try:
        return await asyncio.to_thread(_score_sync, query, documents)
    except Exception as exc:  # a broken reranker must not take retrieval down with it
        logger.warning("reranker unavailable, keeping fused order: %s", exc)
        return None


def relevance_probability(logit: float) -> float:
    return 1.0 / (1.0 + math.exp(-logit))
