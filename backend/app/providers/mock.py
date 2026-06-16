import hashlib
import math
import re
from typing import AsyncIterator, List, Tuple

from app.config import settings
from app.providers.base import AIProvider

_CHUNK_RE = re.compile(
    r"\[([0-9a-f-]{36})\] \(from ([^)]+)\):\n(.*?)(?=\n\n---|\Z)",
    re.DOTALL | re.IGNORECASE,
)


class MockProvider(AIProvider):
    provider_name = "mock"

    @property
    def chat_model_name(self) -> str:
        return "mock-extractive"

    @property
    def embed_model_name(self) -> str:
        return f"mock-{settings.EMBEDDING_DIMENSIONS}d"

    def _deterministic_embedding(self, text: str) -> List[float]:
        dim = settings.EMBEDDING_DIMENSIONS
        digest = hashlib.sha256(text.encode()).digest()
        values = []
        for i in range(dim):
            seed = digest[i % len(digest)] + i
            values.append(math.sin(seed) * 0.5)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._deterministic_embedding(t) for t in texts]

    async def embed_single(self, text: str) -> List[float]:
        return self._deterministic_embedding(text)

    def _parse_context_chunks(self, context: str) -> List[Tuple[str, str, str]]:
        return [(m.group(1), m.group(2), m.group(3).strip()) for m in _CHUNK_RE.finditer(context)]

    _STOPWORDS = frozenset(
        {
            "what", "when", "where", "which", "who", "whom", "whose", "how", "why",
            "is", "are", "was", "were", "the", "a", "an", "do", "does", "did",
            "can", "could", "would", "should", "tell", "about", "me", "my",
        }
    )

    def _select_chunks(self, chunks: List[Tuple[str, str, str]], question: str) -> List[Tuple[str, str, str]]:
        terms = []
        for word in re.findall(r"[a-z0-9']+", question.lower()):
            cleaned = re.sub(r"'s$", "", word.strip("'"))
            if len(cleaned) > 2 and cleaned not in self._STOPWORDS:
                terms.append(cleaned)
        scored = []
        for chunk_id, filename, text in chunks:
            text_lower = text.lower()
            hits = sum(1 for term in terms if term in text_lower) if terms else 1
            scored.append((hits, chunk_id, filename, text))
        scored.sort(key=lambda item: item[0], reverse=True)
        relevant = [item for item in scored if item[0] > 0][:3]
        if relevant:
            return [(chunk_id, filename, text) for _, chunk_id, filename, text in relevant]
        # Preserve retrieval order when no keyword hit (context is already ranked).
        return [(chunk_id, filename, text) for chunk_id, filename, text in chunks[:3]]

    def _answer_from_context(self, question: str, context: str) -> str:
        chunks = self._parse_context_chunks(context)
        if not chunks:
            return "I don't have that information in the current knowledge base."

        selected = self._select_chunks(chunks, question)
        parts = [text for _, _, text in selected]
        citations = " ".join(f"[source:{chunk_id}]" for chunk_id, _, _ in selected)
        return f"{' '.join(parts)} {citations}".strip()

    async def chat_completion(self, messages: list, max_tokens: int = 1000) -> str:
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        context = next((m["content"] for m in messages if m["role"] == "system"), "")
        return self._answer_from_context(user_msg, context)

    async def chat_completion_stream(self, messages: list, max_tokens: int = 1000) -> AsyncIterator[str]:
        full = await self.chat_completion(messages, max_tokens)
        for word in full.split(" "):
            yield word + " "

    def count_tokens(self, text: str) -> int:
        return max(1, len(text.split()))
