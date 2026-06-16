from typing import AsyncIterator, List

from openai import AsyncOpenAI

from app.config import settings
from app.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @property
    def chat_model_name(self) -> str:
        return settings.CHAT_MODEL

    @property
    def embed_model_name(self) -> str:
        return settings.EMBEDDING_MODEL

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        return [item.embedding for item in response.data]

    async def embed_single(self, text: str) -> List[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        response = await self.client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=settings.CHAT_MODEL,
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
        try:
            import tiktoken

            enc = tiktoken.encoding_for_model(settings.CHAT_MODEL)
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text.split()))
