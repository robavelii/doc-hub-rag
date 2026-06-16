import httpx

from app.config import settings
from app.providers.fallback_provider import FallbackProvider
from app.providers.factory import get_ai_provider


async def check_ollama_reachable() -> dict:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return {"reachable": False, "error": f"HTTP {response.status_code}"}
            models = [m.get("name", "") for m in response.json().get("models", [])]
            return {
                "reachable": True,
                "models": models,
                "chat_model": settings.OLLAMA_CHAT_MODEL,
                "embed_model": settings.OLLAMA_EMBED_MODEL,
            }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


async def get_provider_health() -> dict:
    provider = get_ai_provider()
    chat_chain = settings.chat_provider_chain_list
    embedding_provider = settings.embedding_provider_name

    health = {
        "ai_provider": settings.AI_PROVIDER,
        "chat_provider_chain": chat_chain,
        "embedding_provider": embedding_provider,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
            "chat_model": settings.CHAT_MODEL,
            "embed_model": settings.EMBEDDING_MODEL,
        },
        "ollama": await check_ollama_reachable(),
    }

    if isinstance(provider, FallbackProvider):
        health["active_chat_providers"] = provider.chat_provider_names
        health["active_embedding_provider"] = provider.embedding_provider_name

    return health
