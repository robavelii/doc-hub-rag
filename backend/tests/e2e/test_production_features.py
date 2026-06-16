"""E2E tests for production feature endpoints."""
import pytest
from httpx import AsyncClient

from tests.e2e.helpers import auth_headers, register_tenant, unique_email

pytestmark = pytest.mark.e2e


class TestConversations:
    async def test_conversation_crud_and_rename(self, client: AsyncClient):
        reg = await register_tenant(client, "Convo Co", unique_email("convo"))
        token = reg["access_token"]

        r = await client.post("/conversations", headers=auth_headers(token), json={"title": "Test"})
        assert r.status_code == 200
        convo_id = r.json()["id"]

        r = await client.get(f"/conversations/{convo_id}", headers=auth_headers(token))
        assert r.status_code == 200

        r = await client.patch(
            f"/conversations/{convo_id}",
            headers=auth_headers(token),
            json={"title": "Renamed"},
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Renamed"

        r = await client.delete(f"/conversations/{convo_id}", headers=auth_headers(token))
        assert r.status_code == 200


class TestApiKeys:
    async def test_api_key_lifecycle(self, client: AsyncClient):
        reg = await register_tenant(client, "Keys Co", unique_email("keys"))
        token = reg["access_token"]

        r = await client.post("/api-keys", headers=auth_headers(token), json={"name": "Test Key"})
        assert r.status_code == 200
        key_id = r.json()["id"]
        raw_key = r.json()["api_key"]

        r = await client.get("/api-keys", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

        r = await client.post("/query", headers={"X-API-Key": raw_key}, json={"question": "hello"})
        assert r.status_code in (200, 429)

        r = await client.delete(f"/api-keys/{key_id}", headers=auth_headers(token))
        assert r.status_code == 200


class TestWidgetConfig:
    async def test_widget_put_get_roundtrip(self, client: AsyncClient):
        reg = await register_tenant(client, "Widget Co", unique_email("widget"))
        token = reg["access_token"]

        r = await client.put(
            "/widget/config",
            headers=auth_headers(token),
            json={"welcome_message": "Hello from test", "allowed_domains": ["example.com"]},
        )
        assert r.status_code == 200
        assert r.json()["welcome_message"] == "Hello from test"

        r = await client.get("/widget/config", headers=auth_headers(token))
        assert r.status_code == 200
        assert "example.com" in r.json()["allowed_domains"]


class TestFeedback:
    async def test_feedback_submission(self, client: AsyncClient):
        reg = await register_tenant(client, "Feedback Co", unique_email("feedback"))
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        from tests.e2e.helpers import ingest_text_sync, SAMPLE_DOC

        ingest_text_sync(tenant_id, "fb.txt", SAMPLE_DOC)
        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "What is Acme's refund policy?"},
        )
        assert r.status_code == 200
        query_log_id = r.json().get("query_log_id")
        if not query_log_id:
            pytest.skip("Query log id not returned (cached response)")

        r = await client.post(
            "/feedback",
            headers=auth_headers(token),
            json={"query_log_id": query_log_id, "rating": 1},
        )
        assert r.status_code == 200

        r = await client.post(
            "/feedback",
            headers=auth_headers(token),
            json={"query_log_id": query_log_id, "rating": -1},
        )
        assert r.status_code in (400, 409, 422)


class TestRefreshRotation:
    async def test_refresh_token_rotation(self, client: AsyncClient):
        email = unique_email("refresh")
        reg = await register_tenant(client, "Refresh Co", email)
        old_refresh = reg["refresh_token"]

        r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 200
        new_refresh = r.json()["refresh_token"]
        assert new_refresh != old_refresh

        r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 401
