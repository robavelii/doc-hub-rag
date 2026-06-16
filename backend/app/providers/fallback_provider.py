import asyncio
import logging
from typing import AsyncIterator, List, Optional

from app.config import settings
from app.providers.base import AIProvider

logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    """Chat fallback chain with dimension-safe embedding fallback to mock only."""

    provider_name = "fallback"

    def __init__(
        self,
        chat_providers: List[AIProvider],
        embedding_provider: AIProvider,
        mock_provider: AIProvider,
        timeout_seconds: int | None = None,
    ) -> None:
        self._chat_providers = chat_providers
        self._embedding_provider = embedding_provider
        self._mock_provider = mock_provider
        self._timeout = timeout_seconds or settings.PROVIDER_TIMEOUT_SECONDS
        self.last_chat_provider: Optional[str] = None
        self.last_chat_model: Optional[str] = None
        self.last_embed_provider: Optional[str] = None
        self.last_embed_model: Optional[str] = None

    def _provider_label(self, provider: AIProvider) -> str:
        return getattr(provider, "provider_name", provider.__class__.__name__)

    def _chat_model(self, provider: AIProvider) -> str:
        return getattr(provider, "chat_model_name", "unknown")

    def _embed_model(self, provider: AIProvider) -> str:
        return getattr(provider, "embed_model_name", settings.EMBEDDING_MODEL)

    def _record_chat(self, provider: AIProvider) -> None:
        self.last_chat_provider = self._provider_label(provider)
        self.last_chat_model = self._chat_model(provider)

    def _record_embed(self, provider: AIProvider) -> None:
        self.last_embed_provider = self._provider_label(provider)
        self.last_embed_model = self._embed_model(provider)

    @property
    def chat_provider_names(self) -> List[str]:
        return [self._provider_label(p) for p in self._chat_providers]

    @property
    def embedding_provider_name(self) -> str:
        return self._provider_label(self._embedding_provider)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        try:
            result = await asyncio.wait_for(
                self._embedding_provider.embed_texts(texts),
                timeout=self._timeout,
            )
            self._record_embed(self._embedding_provider)
            return result
        except Exception as exc:
            logger.warning(
                "Embedding provider %s failed (%s); falling back to mock",
                self._provider_label(self._embedding_provider),
                exc,
            )
            result = await self._mock_provider.embed_texts(texts)
            self._record_embed(self._mock_provider)
            return result

    async def embed_single(self, text: str) -> List[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        errors: list[str] = []
        for provider in self._chat_providers:
            name = self._provider_label(provider)
            try:
                result = await asyncio.wait_for(
                    provider.chat_completion(messages, max_tokens=max_tokens),
                    timeout=self._timeout,
                )
                self._record_chat(provider)
                return result
            except Exception as exc:
                errors.append(f"{name}: {exc!r}")
                logger.warning("Chat provider %s failed: %r", name, exc)

        raise RuntimeError("All chat providers failed: " + "; ".join(errors))

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        errors: list[str] = []
        for provider in self._chat_providers:
            name = self._provider_label(provider)
            try:
                got_chunk = False
                stream = provider.chat_completion_stream(messages, max_tokens=max_tokens)
                async for chunk in stream:
                    if not got_chunk:
                        self._record_chat(provider)
                        got_chunk = True
                    yield chunk
                if got_chunk:
                    return
                errors.append(f"{name}: empty stream")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                logger.warning("Chat stream provider %s failed: %s", name, exc)

        raise RuntimeError("All chat stream providers failed: " + "; ".join(errors))

    def count_tokens(self, text: str) -> int:
        for provider in reversed(self._chat_providers):
            if hasattr(provider, "count_tokens"):
                return provider.count_tokens(text)
        return max(1, len(text.split()))
