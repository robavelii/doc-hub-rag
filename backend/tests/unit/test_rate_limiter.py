import pytest
from fastapi import HTTPException

from app.middleware import rate_limiter


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_429(monkeypatch):
    class FakeRedis:
        def pipeline(self):
            return self

        async def zremrangebyscore(self, *args, **kwargs):
            return self

        async def zadd(self, *args, **kwargs):
            return self

        async def zcard(self, *args, **kwargs):
            return 100

        async def expire(self, *args, **kwargs):
            return self

        async def execute(self):
            return [0, True, 100, True]

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(rate_limiter, "get_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc:
        await rate_limiter._enforce_rate_limit("test:key", limit=10)
    assert exc.value.status_code == 429
