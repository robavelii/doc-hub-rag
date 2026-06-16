import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.config import settings
from app.main import app


@pytest.fixture(scope="session")
def e2e_services_available():
    """Sync check avoids event-loop conflicts with pytest-asyncio."""
    try:
        engine = create_engine(settings.DATABASE_SYNC_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("E2E tests require Postgres (docker compose -f docker-compose.dev.yml up -d)")


@pytest_asyncio.fixture
async def client(e2e_services_available):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as ac:
        yield ac


@pytest.fixture
def superadmin_creds():
    return {
        "email": settings.SUPERADMIN_EMAIL,
        "password": settings.SUPERADMIN_PASSWORD,
    }
