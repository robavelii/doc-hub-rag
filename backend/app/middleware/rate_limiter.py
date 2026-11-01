import time
import uuid
from collections.abc import Callable

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.dependencies import KIND_PUBLISHABLE_KEY, Principal, resolve_principal
from app.models.tenant import Tenant
from app.services.usage_service import PLAN_LIMITS

_redis: aioredis.Redis | None = None

WINDOW_SECONDS = 60

BUCKET_DEFAULTS = {
    "query": None,
    "documents": 30,
    "auth": 20,
}

# Per-visitor cap for public widget traffic, so one visitor cannot burn the
# whole tenant's quota. Requires the real client IP: run uvicorn/gunicorn with
# FORWARDED_ALLOW_IPS set to the reverse proxy's address.
WIDGET_PER_IP_LIMIT = 20


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _bucket_limit(bucket: str, tenant: Tenant | None = None) -> int:
    if bucket == "query" and tenant:
        plan_limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
        return plan_limits["rate"]
    return BUCKET_DEFAULTS.get(bucket, 60) or 60


async def _sliding_window_count(key: str, limit: int, window: int = WINDOW_SECONDS) -> int:
    r = await get_redis()
    now = time.time()
    member = f"{now}:{uuid.uuid4().hex}"
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return int(results[2])


async def _enforce_rate_limit(key: str, limit: int) -> None:
    try:
        count = await _sliding_window_count(key, limit)
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail={"message": "Rate limit exceeded", "retry_after": WINDOW_SECONDS},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Rate limiting unavailable",
        ) from exc


async def enforce_ip_rate_limit(bucket: str, request: Request, limit: int | None = None) -> None:
    client_ip = request.client.host if request.client else "unknown"
    effective_limit = limit or BUCKET_DEFAULTS.get(bucket, 20) or 20
    key = f"ratelimit:ip:{bucket}:{client_ip}"
    await _enforce_rate_limit(key, effective_limit)


async def enforce_email_rate_limit(bucket: str, email: str, limit: int = 10) -> None:
    key = f"ratelimit:email:{bucket}:{email.lower()}"
    await _enforce_rate_limit(key, limit)


def rate_limit(bucket: str) -> Callable:
    async def _dependency(
        request: Request,
        principal: Principal = Depends(resolve_principal),
    ) -> None:
        tenant = principal.tenant
        limit = _bucket_limit(bucket, tenant)
        key = f"ratelimit:tenant:{tenant.id}:{bucket}"
        await _enforce_rate_limit(key, limit)
        if principal.kind == KIND_PUBLISHABLE_KEY:
            client_ip = request.client.host if request.client else "unknown"
            await _enforce_rate_limit(f"ratelimit:widget:{tenant.id}:{client_ip}", WIDGET_PER_IP_LIMIT)

    return _dependency
