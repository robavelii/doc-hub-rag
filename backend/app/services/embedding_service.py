from typing import List

from app.providers import get_ai_provider


async def embed_chunks(texts: List[str]) -> List[List[float]]:
    provider = get_ai_provider()
    return await provider.embed_texts(texts)


async def embed_single(text: str) -> List[float]:
    provider = get_ai_provider()
    return await provider.embed_single(text)
