from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AIProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        pass

    @abstractmethod
    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        pass

    @abstractmethod
    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass
