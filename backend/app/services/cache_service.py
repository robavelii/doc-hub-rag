import json

import redis.asyncio as redis

from app.config import settings

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def get_cache(key: str) -> str | None:
    client = await get_redis()
    return await client.get(f"rag:{key}")


async def set_cache(key: str, value: str, ttl: int = 3600) -> None:
    client = await get_redis()
    await client.setex(f"rag:{key}", ttl, value)


async def delete_cache(key: str) -> None:
    client = await get_redis()
    await client.delete(f"rag:{key}")


async def get_cache_json(key: str) -> dict | None:
    raw = await get_cache(key)
    return json.loads(raw) if raw else None
