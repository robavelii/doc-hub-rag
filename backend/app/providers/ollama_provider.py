from typing import AsyncIterator, List

from openai import AsyncOpenAI

from app.config import settings
from app.providers.base import AIProvider


class OllamaProvider(AIProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        self.client = AsyncOpenAI(base_url=f"{base}/v1", api_key="ollama")
        self._chat_model = settings.OLLAMA_CHAT_MODEL
        self._embed_model = settings.OLLAMA_EMBED_MODEL

    @property
    def chat_model_name(self) -> str:
        return self._chat_model

    @property
    def embed_model_name(self) -> str:
        return self._embed_model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=self._embed_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def embed_single(self, text: str) -> List[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def count_tokens(self, text: str) -> int:
        return max(1, len(text.split()))
