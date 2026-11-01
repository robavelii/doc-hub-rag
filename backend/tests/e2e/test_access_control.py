"""
Phase 0 access-control and correctness guarantees, exercised through the API:

- publishable (widget) keys can ask questions and read widget config, nothing else
- conversations are private to the user who created them
- members cannot change the knowledge base
- cached answers are invalidated when documents change
- re-ingesting keeps the old chunks searchable until the new ones replace them
"""

import uuid

import pytest
from httpx import AsyncClient

from app.database import AdminSyncSession
from app.models.user import User
from app.services.auth_service import hash_password
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

PASSWORD = "testpass12345"


def create_user(tenant_id: str, email: str, role: str) -> None:
    with AdminSyncSession() as db:
        db.add(
            User(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                email=email,
                password_hash=hash_password(PASSWORD),
                role=role,
                email_verified=True,
            )
        )


async def _tenant_with_doc(client: AsyncClient, name: str) -> dict:
    reg = await register_tenant(client, name, unique_email(name.lower().replace(" ", "")), PASSWORD)
    doc_id = ingest_text_sync(reg["tenant"]["id"], "handbook.txt", SAMPLE_DOC)
    return {**reg, "doc_id": doc_id}


class TestPublishableWidgetKey:
    async def test_registration_returns_a_publishable_widget_key(self, client: AsyncClient):
        reg = await register_tenant(client, "Keys Co", unique_email("keys"), PASSWORD)
        assert reg["widget_key"].startswith("pk_")
        assert reg["api_key"].startswith("sk_")

    async def test_widget_key_can_query_and_read_config(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Widget Query Co")
        headers = api_key_headers(t["widget_key"])

        r = await client.post("/query", headers=headers, json={"question": "What is the refund policy?"})
        assert r.status_code == 200, r.text
        assert r.json()["conversation_id"] is None  # anonymous visitors leave no stored conversation

        r = await client.get("/widget/config", headers=headers)
        assert r.status_code == 200

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/documents"),
            ("GET", "/documents/{doc_id}"),
            ("GET", "/documents/{doc_id}/chunks"),
            ("DELETE", "/documents/{doc_id}"),
            ("POST", "/documents/{doc_id}/reingest"),
            ("GET", "/conversations"),
            ("GET", "/usage/summary"),
            ("GET", "/api-keys"),
        ],
    )
    async def test_widget_key_cannot_touch_documents_or_conversations(
        self, client: AsyncClient, method: str, path: str
    ):
        t = await _tenant_with_doc(client, "Widget Locked Co")
        r = await client.request(method, path.format(doc_id=t["doc_id"]), headers=api_key_headers(t["widget_key"]))
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"

        # The document is still there.
        r = await client.get(f"/documents/{t['doc_id']}", headers=auth_headers(t["access_token"]))
        assert r.status_code == 200

    async def test_widget_key_cannot_upload(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Widget Upload Co")
        r = await client.post(
            "/documents",
            headers=api_key_headers(t["widget_key"]),
            files={"file": ("x.txt", b"injected content", "text/plain")},
        )
        assert r.status_code == 403

    async def test_widget_key_cannot_inject_a_users_conversation(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Widget Convo Co")
        r = await client.post(
            "/query",
            headers=auth_headers(t["access_token"]),
            json={"question": "Secret salary question about the refund policy"},
        )
        convo_id = r.json()["conversation_id"]

        r = await client.post(
            "/query",
            headers=api_key_headers(t["widget_key"]),
            json={"question": "What did I ask before?", "conversation_id": convo_id},
        )
        assert r.status_code == 200
        assert r.json()["conversation_id"] is None

        r = await client.get(f"/conversations/{convo_id}", headers=auth_headers(t["access_token"]))
        assert len(r.json()["messages"]) == 2  # widget call did not append to it

    async def test_widget_key_respects_domain_allowlist(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Widget Domain Co")
        r = await client.put(
            "/widget/config", headers=auth_headers(t["access_token"]), json={"allowed_domains": ["acme.com"]}
        )
        assert r.status_code == 200
        r = await client.get(
            "/widget/config", headers={**api_key_headers(t["widget_key"]), "Origin": "https://evil.example"}
        )
        assert r.status_code == 403
        r = await client.get(
            "/widget/config", headers={**api_key_headers(t["widget_key"]), "Origin": "https://acme.com"}
        )
        assert r.status_code == 200

    async def test_secret_key_still_has_full_api_access(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Secret Key Co")
        r = await client.get("/documents", headers=api_key_headers(t["api_key"]))
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_created_publishable_key_is_query_only(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Created Key Co")
        r = await client.post(
            "/api-keys", headers=auth_headers(t["access_token"]), json={"name": "site", "kind": "publishable"}
        )
        assert r.status_code == 200
        key = r.json()["api_key"]
        assert key.startswith("pk_")
        assert (await client.get("/documents", headers=api_key_headers(key))).status_code == 403
        assert (
            await client.post("/query", headers=api_key_headers(key), json={"question": "refund policy?"})
        ).status_code == 200


class TestConversationPrivacy:
    async def test_members_cannot_see_each_others_conversations(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Privacy Co")
        tenant_id = t["tenant"]["id"]
        alice, bob = unique_email("alice"), unique_email("bob")
        create_user(tenant_id, alice, "member")
        create_user(tenant_id, bob, "member")
        alice_token = (await login(client, alice, PASSWORD))["access_token"]
        bob_token = (await login(client, bob, PASSWORD))["access_token"]

        r = await client.post(
            "/query", headers=auth_headers(alice_token), json={"question": "What is the refund policy?"}
        )
        alice_convo = r.json()["conversation_id"]

        r = await client.get("/conversations", headers=auth_headers(bob_token))
        assert alice_convo not in [c["id"] for c in r.json()]
        for method in ("GET", "DELETE"):
            r = await client.request(method, f"/conversations/{alice_convo}", headers=auth_headers(bob_token))
            assert r.status_code == 404
        r = await client.patch(
            f"/conversations/{alice_convo}", headers=auth_headers(bob_token), json={"title": "hijacked"}
        )
        assert r.status_code == 404

        # Owner of the tenant cannot read it either.
        r = await client.get(f"/conversations/{alice_convo}", headers=auth_headers(t["access_token"]))
        assert r.status_code == 404

        # Bob passing Alice's id to /query starts his own conversation instead of appending.
        r = await client.post(
            "/query",
            headers=auth_headers(bob_token),
            json={"question": "continue", "conversation_id": alice_convo},
        )
        assert r.json()["conversation_id"] != alice_convo
        r = await client.get(f"/conversations/{alice_convo}", headers=auth_headers(alice_token))
        assert len(r.json()["messages"]) == 2


class TestDocumentRoles:
    async def test_member_can_read_but_not_change_documents(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Roles Co")
        member = unique_email("member")
        create_user(t["tenant"]["id"], member, "member")
        token = (await login(client, member, PASSWORD))["access_token"]

        assert (await client.get("/documents", headers=auth_headers(token))).status_code == 200
        assert (await upload_txt_file(client, token, "m.txt", "member upload")).status_code == 403
        assert (await client.delete(f"/documents/{t['doc_id']}", headers=auth_headers(token))).status_code == 403
        assert (
            await client.post(f"/documents/{t['doc_id']}/reingest", headers=auth_headers(token))
        ).status_code == 403
        r = await client.post("/documents/url", headers=auth_headers(token), json={"url": "https://example.com"})
        assert r.status_code == 403

    async def test_admin_can_change_documents(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Admin Roles Co")
        admin = unique_email("admin")
        create_user(t["tenant"]["id"], admin, "admin")
        token = (await login(client, admin, PASSWORD))["access_token"]
        r = await upload_txt_file(client, token, "a.txt", "Admins can upload documents about onboarding.")
        assert r.status_code == 200, r.text


class TestUploadIngestion:
    async def test_upload_runs_full_pipeline_to_ready(self, client: AsyncClient):
        reg = await register_tenant(client, "Pipeline Co", unique_email("pipeline"), PASSWORD)
        token = reg["access_token"]
        r = await upload_txt_file(client, token, "policy.txt", SAMPLE_DOC)
        assert r.status_code == 200, r.text
        doc_id = r.json()["id"]
        r = await client.get(f"/documents/{doc_id}", headers=auth_headers(token))
        assert r.json()["status"] == "ready", r.json()
        assert r.json()["chunk_count"] >= 1


class TestCacheInvalidation:
    async def test_deleting_a_document_invalidates_cached_answers(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Cache Co")
        headers = auth_headers(t["access_token"])
        q = {"question": "What is the refund policy?"}

        first = (await client.post("/query", headers=headers, json=q)).json()
        assert first["from_cache"] is False
        second = (await client.post("/query", headers=headers, json=q)).json()
        assert second["from_cache"] is True

        assert (await client.delete(f"/documents/{t['doc_id']}", headers=headers)).status_code == 200
        third = (await client.post("/query", headers=headers, json=q)).json()
        assert third["from_cache"] is False
        assert third["sources"] == []

    async def test_follow_up_in_a_conversation_is_not_served_from_another_context(self, client: AsyncClient):
        t = await _tenant_with_doc(client, "Cache Context Co")
        headers = auth_headers(t["access_token"])
        await client.post("/query", headers=headers, json={"question": "tell me more"})
        r = await client.post("/query", headers=headers, json={"question": "What is the refund policy?"})
        convo = r.json()["conversation_id"]
        r = await client.post("/query", headers=headers, json={"question": "tell me more", "conversation_id": convo})
        assert r.json()["from_cache"] is False


class TestAtomicReingest:
    async def test_reingest_keeps_chunks_until_replaced(self, client: AsyncClient):
        from app.workers import ingest_task

        t = await _tenant_with_doc(client, "Reingest Co")
        headers = auth_headers(t["access_token"])
        before = (await client.get(f"/documents/{t['doc_id']}", headers=headers)).json()["chunk_count"]
        assert before >= 1

        # Reingest with an embedding outage: the task fails, old chunks must survive.
        def broken(_chunks, _filename):
            raise RuntimeError("embedding provider down")

        original = ingest_task._embed_chunks
        ingest_task._embed_chunks = broken
        try:
            await client.post(f"/documents/{t['doc_id']}/reingest", headers=headers)
        finally:
            ingest_task._embed_chunks = original

        chunks = (await client.get(f"/documents/{t['doc_id']}/chunks", headers=headers)).json()
        assert len(chunks) == before
        r = await client.post("/query", headers=headers, json={"question": "What is the refund policy?"})
        assert r.json()["sources"], "old chunks should still answer questions"
