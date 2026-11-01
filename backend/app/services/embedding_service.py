
from app.providers import get_ai_provider


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    provider = get_ai_provider()
    return await provider.embed_texts(texts)

