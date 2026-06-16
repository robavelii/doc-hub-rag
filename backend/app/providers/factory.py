import logging
from functools import lru_cache

import httpx

from app.config import settings
from app.providers.base import AIProvider
from app.providers.fallback_provider import FallbackProvider
from app.providers.mock import MockProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

OLLAMA_EMBED_DIM = 768


def _ollama_reachable() -> bool:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=2.0) as client:
            return client.get(url).status_code == 200
    except Exception:
        return False


def _build_chat_provider(name: str) -> AIProvider | None:
    if name == "openai":
        if not settings.OPENAI_API_KEY:
            return None
        return OpenAIProvider()
    if name == "ollama":
        if not _ollama_reachable():
            return None
        return OllamaProvider()
    if name == "mock":
        return MockProvider()
    return None


def _build_embedding_provider() -> AIProvider:
    mock = MockProvider()
    chain = [settings.embedding_provider_name]
    if "openai" not in chain and settings.OPENAI_API_KEY:
        chain.insert(0, "openai")
    if "ollama" not in chain:
        chain.append("ollama")
    chain.append("mock")

    seen: set[str] = set()
    for name in chain:
        if name in seen:
            continue
        seen.add(name)
        if name == "openai":
            if not settings.OPENAI_API_KEY:
                continue
            return OpenAIProvider()
        if name == "ollama":
            if not _ollama_reachable():
                continue
            if settings.EMBEDDING_DIMENSIONS != OLLAMA_EMBED_DIM:
                logger.warning(
                    "Ollama embeddings require EMBEDDING_DIMENSIONS=%s (current: %s). "
                    "Run: alembic upgrade head && python scripts/reembed_documents.py",
                    OLLAMA_EMBED_DIM,
                    settings.EMBEDDING_DIMENSIONS,
                )
                continue
            return OllamaProvider()
    return mock


@lru_cache
def get_ai_provider() -> AIProvider:
    mock = MockProvider()
    chat_providers: list[AIProvider] = []

    for name in settings.chat_provider_chain_list:
        provider = _build_chat_provider(name)
        if provider is None:
            continue
        label = getattr(provider, "provider_name", "")
        if not any(getattr(p, "provider_name", "") == label for p in chat_providers):
            chat_providers.append(provider)

    if not chat_providers:
        chat_providers = [mock]

    embedding_provider = _build_embedding_provider()

    return FallbackProvider(
        chat_providers=chat_providers,
        embedding_provider=embedding_provider,
        mock_provider=mock,
        timeout_seconds=settings.PROVIDER_TIMEOUT_SECONDS,
    )
