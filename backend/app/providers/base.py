from abc import ABC, abstractmethod
from typing import AsyncIterator, List


class AIProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
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
