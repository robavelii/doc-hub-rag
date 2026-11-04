from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    """Any API that speaks the OpenAI chat-completions protocol.

    The factory builds one per configured backend (OpenAI itself, Gemini's
    OpenAI-compatible endpoint, or a generic base URL such as OpenRouter or Groq),
    so switching chat provider is an .env change. Embeddings only make sense for
    OpenAI's own models; other backends are used for chat.
    """

    def __init__(
        self,
        provider_name: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
        chat_model: str | None = None,
        reasoning_effort: str = "",
    ) -> None:
        self.provider_name = provider_name
        self.client = AsyncOpenAI(
            api_key=api_key if api_key is not None else settings.OPENAI_API_KEY,
            base_url=base_url or None,
        )
        self._chat_model = chat_model or settings.CHAT_MODEL
        # Thinking models (e.g. Gemini 2.5) spend max_tokens on reasoning first;
        # without a low effort a short answer budget can come back empty.
        self._extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}

    @property
    def chat_model_name(self) -> str:
        return self._chat_model

    @property
    def embed_model_name(self) -> str:
        return settings.EMBEDDING_MODEL

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        return [item.embedding for item in response.data]

    async def embed_single(self, text: str) -> list[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
            **self._extra,
        )
        return response.choices[0].message.content or ""

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
            stream=True,
            **self._extra,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken

            try:
                enc = tiktoken.encoding_for_model(self._chat_model)
            except KeyError:
                # Non-OpenAI models: o200k is a close enough estimate for usage metering.
                enc = tiktoken.get_encoding("o200k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text.split()))
