"""Local, in-process models via fastembed (ONNX, no GPU or API key needed).

- Embeddings: BAAI/bge-small-en-v1.5 by default (384 dimensions).
- Reranking: a MiniLM cross-encoder (see app/services/reranker.py).

Useful for self-hosted deployments that must not send documents to a third
party, and for evaluation runs in CI. Models download once to
LOCAL_MODEL_CACHE_DIR (or the fastembed default cache).
"""

import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache

from app.config import settings
from app.providers.base import AIProvider


@lru_cache(maxsize=2)
def _embedding_model(name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(name, cache_dir=settings.LOCAL_MODEL_CACHE_DIR or None)


class LocalProvider(AIProvider):
    """Embeddings only. Chat must come from another provider in CHAT_PROVIDER_CHAIN."""

    provider_name = "local"

    @property
    def embed_model_name(self) -> str:
        return settings.LOCAL_EMBED_MODEL

    @property
    def chat_model_name(self) -> str:
        return "none"

    def _embed_documents_sync(self, texts: list[str]) -> list[list[float]]:
        model = _embedding_model(settings.LOCAL_EMBED_MODEL)
        return [vector.tolist() for vector in model.passage_embed(texts)]

    def _embed_query_sync(self, text: str) -> list[float]:
        model = _embedding_model(settings.LOCAL_EMBED_MODEL)
        return next(iter(model.query_embed(text))).tolist()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_documents_sync, texts)

    async def embed_single(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]

    async def embed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_query_sync, text)

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        raise NotImplementedError("The local provider only serves embeddings")

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        raise NotImplementedError("The local provider only serves embeddings")
        yield ""  # pragma: no cover

    def count_tokens(self, text: str) -> int:
        return max(1, len(text.split()))
