"""
Extended E2E: document lifecycle, delete, API-key path, conversations, admin.
"""

import pytest
from httpx import AsyncClient

from tests.e2e.helpers import (
    SAMPLE_DOC,
    api_key_headers,
    auth_headers,
    ingest_text_sync,
    login,
    register_tenant,
    unique_email,
    upload_txt_file,
)

pytestmark = pytest.mark.e2e


class TestDocumentLifecycle:
    async def test_upload_delete_and_usage(self, client: AsyncClient):
        email = unique_email("lifecycle")
        reg = await register_tenant(client, "Lifecycle Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        doc_id = ingest_text_sync(tenant_id, "lifecycle.txt", SAMPLE_DOC)

        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

        r = await client.get(f"/documents/{doc_id}/chunks", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

        r = await client.delete(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 404

    async def test_reingest_document(self, client: AsyncClient):
        from app.workers.ingest_task import ingest_notion_page

        email = unique_email("reingest")
        reg = await register_tenant(client, "Reingest Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        doc_id = ingest_text_sync(tenant_id, "reingest.txt", SAMPLE_DOC)

        r = await client.post(f"/documents/{doc_id}/reingest", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        ingest_notion_page.apply(args=[doc_id, tenant_id, SAMPLE_DOC + " Updated.", "reingest.txt"])

        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestApiKeyPath:
    async def test_query_via_api_key(self, client: AsyncClient):
        email = unique_email("apikey")
        reg = await register_tenant(client, "API Key Co", email)
        api_key = reg["api_key"]
        tenant_id = reg["tenant"]["id"]

        ingest_text_sync(tenant_id, "apikey-doc.txt", SAMPLE_DOC)

        r = await client.post(
            "/query",
            headers=api_key_headers(api_key),
            json={"question": "What does Acme offer?"},
        )
        assert r.status_code == 200
        assert "answer" in r.json()


class TestConversationsPersistence:
    async def test_query_persists_conversation(self, client: AsyncClient):
        email = unique_email("convo")
        reg = await register_tenant(client, "Convo Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        ingest_text_sync(tenant_id, "convo-doc.txt", SAMPLE_DOC)

        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "What is the refund policy?"},
        )
        assert r.status_code == 200
        convo_id = r.json().get("conversation_id")
        assert convo_id

        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "Tell me more", "conversation_id": convo_id},
        )
        assert r.status_code == 200
        assert r.json().get("conversation_id") == convo_id

        r = await client.get(f"/conversations/{convo_id}", headers=auth_headers(token))
        assert r.status_code == 200
        messages = r.json().get("messages", [])
        assert len(messages) >= 2


class TestAdminFlows:
    async def test_admin_create_tenant(self, client: AsyncClient, superadmin_creds):
        admin = await login(client, superadmin_creds["email"], superadmin_creds["password"])
        token = admin["access_token"]

        email = unique_email("admin-created")
        r = await client.post(
            "/admin/tenants",
            headers=auth_headers(token),
            json={
                "name": "Admin Created Co",
                "plan": "starter",
                "owner_email": email,
                "owner_password": "securepass123",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Admin Created Co"
        assert "api_key" in body

        owner = await login(client, email, "securepass123")
        assert owner["access_token"]
