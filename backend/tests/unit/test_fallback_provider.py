import pytest

from app.providers.fallback_provider import FallbackProvider
from app.providers.mock import MockProvider


class FailingChatProvider(MockProvider):
    provider_name = "failing"

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        raise RuntimeError("chat unavailable")

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000):
        raise RuntimeError("stream unavailable")
        yield ""  # pragma: no cover


class SuccessChatProvider(MockProvider):
    provider_name = "success"

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        return "success answer"

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000):
        yield "success "
        yield "stream"


class FailingEmbedProvider(MockProvider):
    provider_name = "failing-embed"

    async def embed_texts(self, texts: list) -> list:
        raise RuntimeError("embed unavailable")


@pytest.mark.asyncio
async def test_chat_fallback_uses_second_provider():
    mock = MockProvider()
    provider = FallbackProvider(
        chat_providers=[FailingChatProvider(), SuccessChatProvider()],
        embedding_provider=mock,
        mock_provider=mock,
        timeout_seconds=5,
    )

    answer = await provider.chat_completion([{"role": "user", "content": "hello"}])

    assert answer == "success answer"
    assert provider.last_chat_provider == "success"
    assert provider.last_chat_model == "mock-extractive"


@pytest.mark.asyncio
async def test_chat_stream_fallback():
    mock = MockProvider()
    provider = FallbackProvider(
        chat_providers=[FailingChatProvider(), SuccessChatProvider()],
        embedding_provider=mock,
        mock_provider=mock,
        timeout_seconds=5,
    )

    chunks = []
    async for chunk in provider.chat_completion_stream([{"role": "user", "content": "hello"}]):
        chunks.append(chunk)

    assert "".join(chunks) == "success stream"
    assert provider.last_chat_provider == "success"


@pytest.mark.asyncio
async def test_embedding_falls_back_to_mock():
    mock = MockProvider()
    provider = FallbackProvider(
        chat_providers=[mock],
        embedding_provider=FailingEmbedProvider(),
        mock_provider=mock,
        timeout_seconds=5,
    )

    vector = await provider.embed_single("tenant document text")

    assert len(vector) > 0
    assert provider.last_embed_provider == "mock"


@pytest.mark.asyncio
async def test_all_chat_providers_fail_raises():
    mock = MockProvider()
    provider = FallbackProvider(
        chat_providers=[FailingChatProvider()],
        embedding_provider=mock,
        mock_provider=mock,
        timeout_seconds=5,
    )

    with pytest.raises(RuntimeError, match="All chat providers failed"):
        await provider.chat_completion([{"role": "user", "content": "hello"}])
