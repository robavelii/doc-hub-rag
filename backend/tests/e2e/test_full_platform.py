"""
End-to-end tests for all major API endpoints.

Requires: Postgres + Redis + MinIO running, migrations applied.
Run: pytest tests/e2e -m e2e -v
"""
import pytest
from httpx import AsyncClient

from tests.e2e.helpers import (
    OTHER_TENANT_DOC,
    SAMPLE_DOC,
    api_key_headers,
    auth_headers,
    ingest_text_sync,
    login,
    parse_sse_events,
    register_tenant,
    unique_email,
    upload_txt_file,
)

pytestmark = pytest.mark.e2e


class TestHealthAndAuth:
    async def test_health(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_register_login_refresh(self, client: AsyncClient):
        email = unique_email("auth")
        reg = await register_tenant(client, "Auth Test Co", email)
        assert "access_token" in reg
        assert "api_key" in reg
        assert reg["tenant"]["name"] == "Auth Test Co"

        login_data = await login(client, email)
        assert "access_token" in login_data

        r = await client.post("/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_invalid_credentials(self, client: AsyncClient):
        r = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
        assert r.status_code == 401


class TestDocumentsAndQuery:
    async def test_document_crud_and_query_flow(self, client: AsyncClient):
        email = unique_email("docs")
        reg = await register_tenant(client, "Docs Test Co", email)
        token = reg["access_token"]
        tenant_id = reg["tenant"]["id"]

        doc_id = ingest_text_sync(tenant_id, "acme-facts.txt", SAMPLE_DOC)

        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "ready"
        assert r.json()["chunk_count"] >= 1

        r = await client.get("/documents", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

        r = await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "What is Acme's refund policy?"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "answer" in body
        assert len(body.get("sources", [])) >= 0

    async def test_query_stream_sse(self, client: AsyncClient):
        email = unique_email("stream")
        reg = await register_tenant(client, "Stream Test Co", email)
        token = reg["access_token"]
        ingest_text_sync(reg["tenant"]["id"], "stream-doc.txt", SAMPLE_DOC)

        response = await client.post(
            "/query/stream",
            headers=auth_headers(token),
            json={"question": "When was Acme founded?"},
        )
        assert response.status_code == 200
        events = parse_sse_events(response.text)
        assert any(e.get("type") == "chunk" for e in events)
        assert any(e.get("type") == "done" for e in events)

    async def test_file_upload(self, client: AsyncClient):
        email = unique_email("upload")
        reg = await register_tenant(client, "Upload Test Co", email)
        token = reg["access_token"]

        r = await upload_txt_file(
            client, token, "uploaded.txt", "Uploaded file content about widgets and gadgets."
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        doc_id = r.json()["id"]

        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["filename"] == "uploaded.txt"

    async def test_url_ingest_endpoint(self, client: AsyncClient):
        email = unique_email("url")
        reg = await register_tenant(client, "URL Test Co", email)
        token = reg["access_token"]

        r = await client.post(
            "/documents/url",
            headers=auth_headers(token),
            json={"url": "https://example.com"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"


class TestUsageAndWidget:
    async def test_usage_endpoints(self, client: AsyncClient):
        email = unique_email("usage")
        reg = await register_tenant(client, "Usage Test Co", email)
        token = reg["access_token"]
        ingest_text_sync(reg["tenant"]["id"], "usage-doc.txt", SAMPLE_DOC)

        await client.post(
            "/query",
            headers=auth_headers(token),
            json={"question": "What support does Acme offer?"},
        )

        r = await client.get("/usage/summary", headers=auth_headers(token))
        assert r.status_code == 200
        summary = r.json()
        assert "tokens_used" in summary
        assert "plan" in summary

        r = await client.get("/usage/history", headers=auth_headers(token))
        assert r.status_code == 200
        assert "items" in r.json()

    async def test_widget_config_via_api_key(self, client: AsyncClient):
        email = unique_email("widget")
        reg = await register_tenant(client, "Widget Test Co", email)
        api_key = reg["api_key"]

        r = await client.get("/widget/config", headers=api_key_headers(api_key))
        assert r.status_code == 200
        assert r.json()["tenant_name"] == "Widget Test Co"


class TestAdmin:
    async def test_admin_requires_superadmin(self, client: AsyncClient):
        email = unique_email("notadmin")
        reg = await register_tenant(client, "Regular Co", email)
        token = reg["access_token"]

        r = await client.get("/admin/tenants", headers=auth_headers(token))
        assert r.status_code == 403

    async def test_admin_tenant_list_and_patch(self, client: AsyncClient, superadmin_creds: dict):
        login_data = await login(client, superadmin_creds["email"], superadmin_creds["password"])
        token = login_data["access_token"]

        r = await client.get("/admin/tenants", headers=auth_headers(token))
        assert r.status_code == 200
        tenants = r.json()
        assert isinstance(tenants, list)
        if tenants:
            tid = tenants[0]["id"]
            r = await client.get(f"/admin/tenants/{tid}", headers=auth_headers(token))
            assert r.status_code == 200

        r = await client.get("/admin/usage/global", headers=auth_headers(token))
        assert r.status_code == 200
        assert "total_tenants" in r.json()


class TestTenantIsolation:
    async def test_tenant_a_cannot_see_tenant_b_documents(self, client: AsyncClient):
        email_a = unique_email("tenanta")
        email_b = unique_email("tenantb")

        reg_a = await register_tenant(client, "Tenant A Corp", email_a)
        reg_b = await register_tenant(client, "Tenant B Corp", email_b)

        doc_b = ingest_text_sync(reg_b["tenant"]["id"], "globex-secret.txt", OTHER_TENANT_DOC)
        ingest_text_sync(reg_a["tenant"]["id"], "acme-public.txt", SAMPLE_DOC)

        r = await client.get(f"/documents/{doc_b}", headers=auth_headers(reg_a["access_token"]))
        assert r.status_code == 404

        r = await client.post(
            "/query",
            headers=auth_headers(reg_a["access_token"]),
            json={"question": "What is Globex revenue in 2024?"},
        )
        assert r.status_code == 200
        result = r.json()
        answer = result["answer"].lower()
        source_doc_ids = {s.get("doc_id") for s in result.get("sources", [])}
        # Must not leak Tenant B's document into Tenant A's sources
        assert str(doc_b) not in source_doc_ids
        assert "50 million" not in answer
        assert "confidential to globex" not in answer
        # Sources must only reference Tenant A's own documents
        for src in result.get("sources", []):
            assert "globex" not in (src.get("filename") or "").lower()

    async def test_unauthenticated_request_rejected(self, client: AsyncClient):
        r = await client.get("/documents")
        assert r.status_code == 401
