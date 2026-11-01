import logging
import uuid
from collections.abc import Iterator

import httpx
from sqlalchemy import select

from app.database import AdminSyncSession, SyncSession, set_tenant_rls_sync
from app.models.document import Document
from app.models.integration_token import IntegrationToken
from app.services.encryption_service import decrypt_value
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
PAGE_SIZE = 100
MAX_BLOCK_DEPTH = 5  # nested toggles/columns/lists; deeper content is rare and costly to walk
MAX_PAGES_PER_SYNC = 2000


def _rich_text(content: dict) -> str:
    return "".join(r.get("plain_text", "") for r in content.get("rich_text", []))


def extract_notion_text(blocks: list) -> str:
    """Flatten already-fetched blocks (children inlined under `_children`) to text."""
    lines: list[str] = []

    def walk(items: list, depth: int) -> None:
        for block in items:
            block_type = block.get("type", "")
            content = block.get(block_type, {}) or {}
            text = _rich_text(content)
            if block_type == "child_page":
                text = content.get("title", "")
            elif block_type == "table_row":
                text = " | ".join("".join(c.get("plain_text", "") for c in cell) for cell in content.get("cells", []))
            if text.strip():
                lines.append(("  " * depth) + text)
            walk(block.get("_children", []), depth + 1)

    walk(blocks, 0)
    return "\n\n".join(lines)


def extract_page_title(page: dict) -> str:
    """The title property is named "title" on plain pages but anything (e.g. "Name") in databases."""
    for prop in (page.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
            if title.strip():
                return title.strip()
    return "Untitled"


def _paginate(client: httpx.Client, method: str, url: str, body: dict | None = None) -> Iterator[dict]:
    cursor: str | None = None
    while True:
        if method == "POST":
            payload = {**(body or {}), "page_size": PAGE_SIZE}
            if cursor:
                payload["start_cursor"] = cursor
            response = client.post(url, json=payload)
        else:
            params = {"page_size": PAGE_SIZE}
            if cursor:
                params["start_cursor"] = cursor
            response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        yield from data.get("results", [])
        if not data.get("has_more"):
            return
        cursor = data.get("next_cursor")


def fetch_block_tree(client: httpx.Client, block_id: str, depth: int = 0) -> list[dict]:
    blocks = list(_paginate(client, "GET", f"{NOTION_API}/blocks/{block_id}/children"))
    if depth < MAX_BLOCK_DEPTH:
        for block in blocks:
            # child pages are synced as their own documents
            if block.get("has_children") and block.get("type") != "child_page":
                block["_children"] = fetch_block_tree(client, block["id"], depth + 1)
    return blocks


def _notion_client(access_token: str) -> httpx.Client:
    return httpx.Client(
        headers={"Authorization": f"Bearer {access_token}", "Notion-Version": NOTION_VERSION},
        timeout=30,
    )


@celery.task
def sync_notion(tenant_id: str):
    from app.workers.ingest_task import ingest_notion_page

    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        token_row = db.execute(
            select(IntegrationToken)
            .where(IntegrationToken.tenant_id == tenant_id)
            .where(IntegrationToken.provider == "notion")
        ).scalar_one_or_none()
        if not token_row:
            return

        with _notion_client(decrypt_value(token_row.access_token)) as client:
            pages = _paginate(client, "POST", f"{NOTION_API}/search", {"filter": {"value": "page", "property": "object"}})
            for count, page in enumerate(pages):
                if count >= MAX_PAGES_PER_SYNC:
                    logger.warning("notion sync for tenant %s stopped at %s pages", tenant_id, MAX_PAGES_PER_SYNC)
                    break
                page_id = page["id"]
                last_edited = page.get("last_edited_time")
                title = extract_page_title(page)

                existing = db.execute(
                    select(Document)
                    .where(Document.tenant_id == tenant_id)
                    .where(Document.source_url == page_id)
                    .where(Document.integration == "notion")
                ).scalar_one_or_none()

                if existing and (existing.metadata_ or {}).get("last_edited") == last_edited and existing.status == "ready":
                    continue

                text = extract_notion_text(fetch_block_tree(client, page_id))

                if existing:
                    # Old chunks keep serving until ingestion swaps them atomically.
                    existing.status = "pending"
                    doc_id = existing.id
                else:
                    doc = Document(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        filename=title,
                        file_type="txt",
                        s3_key="",
                        source_url=page_id,
                        integration="notion",
                        status="pending",
                        metadata_={"last_edited": last_edited},
                    )
                    db.add(doc)
                    doc_id = doc.id
                db.commit()
                ingest_notion_page.delay(str(doc_id), tenant_id, text, title, last_edited)


@celery.task
def sync_all_notion():
    with AdminSyncSession() as db:
        tokens = db.execute(select(IntegrationToken).where(IntegrationToken.provider == "notion")).scalars().all()
        tenant_ids = [str(token.tenant_id) for token in tokens]
    for tid in tenant_ids:
        sync_notion.delay(tid)
