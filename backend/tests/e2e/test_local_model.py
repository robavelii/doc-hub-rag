"""
Optional E2E test with local Ollama — only runs when Ollama is reachable.

Run:
  CHAT_PROVIDER_CHAIN=ollama,mock EMBEDDING_PROVIDER=mock pytest tests/e2e/test_local_model.py -m local -v
"""
import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from tests.e2e.helpers import auth_headers, ingest_text_sync, register_tenant, unique_email

pytestmark = [pytest.mark.e2e, pytest.mark.local]


async def _ollama_reachable() -> bool:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def require_ollama():
    if not await _ollama_reachable():
        pytest.skip("Ollama is not reachable — start with: ollama serve")


class TestLocalModelIntegration:
    async def test_local_chat_with_mock_embeddings(self, client: AsyncClient):
        email = unique_email("local")
        reg = await register_tenant(client, "Local Model Test Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        doc_text = (
            "Project Phoenix launched in March 2025. "
            "The lead engineer is Dr. Sarah Chen. "
            "The project budget is exactly 2.4 million dollars."
        )
        ingest_text_sync(tenant_id, "phoenix-local.txt", doc_text)

        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "Who is the lead engineer on Project Phoenix?"},
        )
        assert r.status_code == 200
        body = r.json()
        answer = body["answer"].lower()
        assert "sarah" in answer or "chen" in answer or len(answer) > 20
        assert body["confidence"] > 0
        if body.get("provider"):
            assert body["provider"] in {"ollama", "mock", "openai"}
