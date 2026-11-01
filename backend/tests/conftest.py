import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import admin_engine, engine
from app.main import app
from app.middleware import rate_limiter
from app.providers.factory import get_ai_provider
from app.services import cache_service


@pytest_asyncio.fixture(autouse=True)
async def _reset_shared_async_state():
    """pytest-asyncio creates a fresh event loop per test, but pooled asyncpg
    connections and the global Redis client stay bound to the loop they were
    created on. Dispose them at teardown (inside the test's own loop) so the
    next test starts clean. Also flush rate-limit counters so suites that
    register many tenants don't trip 429s."""
    try:
        r = await rate_limiter.get_redis()
        keys = await r.keys("ratelimit:*")
        if keys:
            await r.delete(*keys)
    except Exception:
        pass

    yield

    if rate_limiter._redis is not None:
        try:
            await rate_limiter._redis.aclose()
        except Exception:
            pass
        rate_limiter._redis = None
    if cache_service._redis_client is not None:
        try:
            await cache_service._redis_client.aclose()
        except Exception:
            pass
        cache_service._redis_client = None
    get_ai_provider.cache_clear()  # AsyncOpenAI clients are loop-bound too
    await engine.dispose()
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_text():
    return "word " * 1000
