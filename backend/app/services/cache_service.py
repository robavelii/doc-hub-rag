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


# --- Corpus versioning -------------------------------------------------------
# Every change to a tenant's documents bumps a counter that is part of the
# answer-cache key, so cached answers never outlive the documents they cite.

def _corpus_key(tenant_id: str) -> str:
    return f"rag:corpus_version:{tenant_id}"


async def get_corpus_version(tenant_id: str) -> int:
    client = await get_redis()
    value = await client.get(_corpus_key(tenant_id))
    return int(value) if value else 0


async def bump_corpus_version(tenant_id: str) -> None:
    client = await get_redis()
    await client.incr(_corpus_key(tenant_id))


def bump_corpus_version_sync(tenant_id: str) -> None:
    """For Celery workers (sync code)."""
    import redis as sync_redis

    client = sync_redis.from_url(settings.REDIS_URL)
    try:
        client.incr(_corpus_key(tenant_id))
    finally:
        client.close()
