"""Every supported format goes upload → S3 → parse → chunk → embed → ready, with section metadata."""

import io

import pytest
from httpx import AsyncClient

from tests.e2e.helpers import auth_headers, register_tenant, unique_email
from tests.unit.test_parsers import EML, HTML, MARKDOWN, _docx, _pptx, _xlsx

pytestmark = pytest.mark.e2e

FILES = [
    ("handbook.docx", _docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Paid Time Off"),
    ("roadmap.pptx", _pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Q3 Roadmap"),
    ("prices.xlsx", _xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Price list"),
    ("runbook.md", lambda: MARKDOWN, "text/markdown", "Rollback"),
    ("faq.html", lambda: HTML, "text/html", "Refunds"),
    ("closure.eml", lambda: EML, "message/rfc822", "Office closure"),
    ("plans.csv", lambda: b"Plan,Price\nStarter,49 USD\n", "text/csv", None),
]


@pytest.mark.parametrize(("filename", "make", "mime", "heading"), FILES)
async def test_upload_each_format_reaches_ready_with_metadata(client: AsyncClient, filename, make, mime, heading):
    reg = await register_tenant(client, "Formats Co", unique_email("formats"))
    headers = auth_headers(reg["access_token"])
    r = await client.post("/documents", headers=headers, files={"file": (filename, io.BytesIO(make()), mime)})
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]

    doc = (await client.get(f"/documents/{doc_id}", headers=headers)).json()
    assert doc["status"] == "ready", doc
    assert doc["chunk_count"] >= 1

    if heading:
        r = await client.post("/query", headers=headers, json={"question": f"What does it say about {heading}?"})
        sources = r.json()["sources"]
        assert sources, r.json()
        assert any(heading in (s.get("heading") or "") for s in sources), sources


async def test_unsupported_binary_is_rejected(client: AsyncClient):
    reg = await register_tenant(client, "Reject Co", unique_email("reject"))
    r = await client.post(
        "/documents",
        headers=auth_headers(reg["access_token"]),
        files={"file": ("tool.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "Supported" in r.json().get("detail", r.json().get("error", ""))
