"""Audit log export and data retention."""

import csv
import io
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database import AdminSyncSession
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation
from app.models.query_log import QueryLog
from app.workers.retention_task import purge_expired_data
from tests.e2e.helpers import auth_headers, login, register_tenant, unique_email
from tests.e2e.test_access_control import PASSWORD, create_user

pytestmark = pytest.mark.e2e


async def _tenant_with_activity(client: AsyncClient) -> dict:
    reg = await register_tenant(client, "Audit Co", unique_email("audit"), PASSWORD)
    h = auth_headers(reg["access_token"])
    await client.post("/collections", headers=h, json={"name": "Legal", "visibility": "restricted"})
    await client.post(
        "/documents", headers=h, files={"file": ("contract.txt", io.BytesIO(b"Contract terms are confidential."), "text/plain")}
    )
    return reg


class TestAuditLog:
    async def test_sensitive_actions_are_recorded_and_listable(self, client: AsyncClient):
        reg = await _tenant_with_activity(client)
        rows = (await client.get("/audit-logs", headers=auth_headers(reg["access_token"]))).json()
        actions = {r["action"] for r in rows}
        assert {"user_registered", "collection_created", "document_uploaded"} <= actions
        assert rows == sorted(rows, key=lambda r: r["created_at"], reverse=True)

    async def test_csv_and_jsonl_export(self, client: AsyncClient):
        reg = await _tenant_with_activity(client)
        h = auth_headers(reg["access_token"])
        r = await client.get("/audit-logs/export", headers=h, params={"format": "csv"})
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(io.StringIO(r.text)))
        assert {row["action"] for row in rows} >= {"user_registered", "document_uploaded"}
        assert all(json.loads(row["details"]) is not None for row in rows)

        r = await client.get("/audit-logs/export", headers=h, params={"format": "jsonl"})
        lines = [json.loads(line) for line in r.text.splitlines()]
        assert lines and lines == sorted(lines, key=lambda x: x["created_at"])
        # The export itself is audited.
        assert "audit_log_exported" in {x["action"] for x in (await client.get("/audit-logs", headers=h)).json()}

    async def test_export_is_tenant_scoped_and_owner_only(self, client: AsyncClient):
        a = await _tenant_with_activity(client)
        b = await _tenant_with_activity(client)
        r = await client.get("/audit-logs/export", headers=auth_headers(a["access_token"]), params={"format": "jsonl"})
        b_user = b["user"]["id"]
        assert all(line and json.loads(line)["user_id"] != b_user for line in r.text.splitlines())

        email = unique_email("member")
        create_user(a["tenant"]["id"], email, "member")
        member = auth_headers((await login(client, email, PASSWORD))["access_token"])
        assert (await client.get("/audit-logs", headers=member)).status_code == 403
        assert (await client.get("/audit-logs/export", headers=member)).status_code == 403


class TestRetention:
    async def test_settings_validation(self, client: AsyncClient):
        reg = await register_tenant(client, "Ret Co", unique_email("ret"), PASSWORD)
        h = auth_headers(reg["access_token"])
        assert (await client.put("/settings/retention", headers=h, json={"audit_retention_days": 7})).status_code == 422
        r = await client.put("/settings/retention", headers=h, json={"content_retention_days": 30, "audit_retention_days": 365})
        assert r.json() == {"content_retention_days": 30, "audit_retention_days": 365}
        assert (await client.get("/settings/retention", headers=h)).json()["content_retention_days"] == 30

    async def test_purge_removes_only_expired_data_of_tenants_with_retention(self, client: AsyncClient):
        keep = await register_tenant(client, "Keep Co", unique_email("keep"), PASSWORD)
        purge = await register_tenant(client, "Purge Co", unique_email("purge"), PASSWORD)
        await client.put(
            "/settings/retention",
            headers=auth_headers(purge["access_token"]),
            json={"content_retention_days": 30, "audit_retention_days": 90},
        )
        old, recent = datetime.now(UTC) - timedelta(days=400), datetime.now(UTC) - timedelta(days=1)
        ids: dict[str, list[uuid.UUID]] = {}
        with AdminSyncSession() as db:
            for name, reg in (("keep", keep), ("purge", purge)):
                tid = uuid.UUID(reg["tenant"]["id"])
                rows = [
                    QueryLog(id=uuid.uuid4(), tenant_id=tid, question="old q", created_at=old),
                    QueryLog(id=uuid.uuid4(), tenant_id=tid, question="new q", created_at=recent),
                    Conversation(id=uuid.uuid4(), tenant_id=tid, title="old", updated_at=old),
                    AuditLog(id=uuid.uuid4(), tenant_id=tid, action="old_action", created_at=old),
                ]
                db.add_all(rows)
                ids[name] = [r.id for r in rows]

        purge_expired_data.apply()

        with AdminSyncSession() as db:
            def exists(model, row_id):
                return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none() is not None

            q_old, q_new, convo, audit = ids["purge"]
            assert not exists(QueryLog, q_old) and exists(QueryLog, q_new)
            assert not exists(Conversation, convo) and not exists(AuditLog, audit)
            k_old, _, k_convo, k_audit = ids["keep"]
            assert exists(QueryLog, k_old) and exists(Conversation, k_convo) and exists(AuditLog, k_audit)
