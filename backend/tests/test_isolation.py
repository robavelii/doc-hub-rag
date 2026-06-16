import uuid

import pytest
from httpx import AsyncClient

from tests.e2e.helpers import auth_headers, ingest_text_sync, register_tenant, unique_email

pytestmark = pytest.mark.e2e


async def test_cross_tenant_document_access_denied(client: AsyncClient):
    reg_a = await register_tenant(client, "Tenant A", unique_email("iso-a"))
    reg_b = await register_tenant(client, "Tenant B", unique_email("iso-b"))

    doc_id = ingest_text_sync(
        reg_a["tenant"]["id"],
        "secret.txt",
        "Tenant A confidential data only.",
    )

    r = await client.get(
        f"/documents/{doc_id}",
        headers=auth_headers(reg_b["access_token"]),
    )
    assert r.status_code == 404
