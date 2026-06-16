"""
Optional E2E test with real OpenAI — only runs when OPENAI_API_KEY is set.

Run:
  AI_PROVIDER=openai OPENAI_API_KEY=sk-... pytest tests/e2e/test_openai_integration.py -m openai -v
"""
import os

import pytest
from httpx import AsyncClient

from tests.e2e.helpers import auth_headers, ingest_text_sync, register_tenant, unique_email

pytestmark = [pytest.mark.e2e, pytest.mark.openai]


@pytest.fixture(autouse=True)
def require_openai():
    if os.getenv("AI_PROVIDER", "mock") != "openai" or not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Set AI_PROVIDER=openai and OPENAI_API_KEY to run OpenAI integration tests")


class TestOpenAIIntegration:
    async def test_real_embedding_and_chat(self, client: AsyncClient):
        email = unique_email("openai")
        reg = await register_tenant(client, "OpenAI Test Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        doc_text = (
            "Project Phoenix launched in March 2025. "
            "The lead engineer is Dr. Sarah Chen. "
            "The project budget is exactly 2.4 million dollars."
        )
        ingest_text_sync(tenant_id, "phoenix-project.txt", doc_text)

        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "Who is the lead engineer on Project Phoenix?"},
        )
        assert r.status_code == 200
        answer = r.json()["answer"].lower()
        assert "sarah" in answer or "chen" in answer
        assert r.json()["confidence"] > 0
