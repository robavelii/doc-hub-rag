import uuid

import httpx
from sqlalchemy import select

from app.database import AdminSyncSession, SyncSession, set_tenant_rls_sync
from app.models.document import Document
from app.models.integration_token import IntegrationToken
from app.services.encryption_service import decrypt_value
from app.services.vector_service import delete_doc_vectors_sync
from app.workers.celery_app import celery


def extract_notion_text(blocks: list) -> str:
    lines = []
    for block in blocks:
        block_type = block.get("type", "")
        content = block.get(block_type, {})
        rich_text = content.get("rich_text", [])
        text = " ".join(r.get("plain_text", "") for r in rich_text)
        if text.strip():
            lines.append(text)
    return "\n\n".join(lines)


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

        access_token = decrypt_value(token_row.access_token)
        headers = {"Authorization": f"Bearer {access_token}", "Notion-Version": "2022-06-28"}
        response = httpx.post(
            "https://api.notion.com/v1/search",
            headers=headers,
            json={"filter": {"value": "page", "property": "object"}},
            timeout=30,
        )
        pages = response.json().get("results", [])

        for page in pages:
            page_id = page["id"]
            last_edited = page.get("last_edited_time")
            title_prop = page.get("properties", {}).get("title", [{}])
            title = title_prop[0].get("plain_text", "Untitled") if title_prop else "Untitled"

            existing = db.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .where(Document.source_url == page_id)
                .where(Document.integration == "notion")
            ).scalar_one_or_none()

            if existing and (existing.metadata_ or {}).get("last_edited") == last_edited:
                continue

            blocks_response = httpx.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=headers,
                timeout=30,
            )
            text = extract_notion_text(blocks_response.json().get("results", []))

            if existing:
                delete_doc_vectors_sync(db, str(existing.id), tenant_id)
                existing.status = "pending"
                existing.metadata_ = {"last_edited": last_edited}
                db.commit()
                ingest_notion_page.delay(str(existing.id), tenant_id, text, title)
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
                db.commit()
                ingest_notion_page.delay(str(doc.id), tenant_id, text, title)


@celery.task
def sync_all_notion():
    with AdminSyncSession() as db:
        tokens = db.execute(
            select(IntegrationToken).where(IntegrationToken.provider == "notion")
        ).scalars().all()
        tenant_ids = [str(token.tenant_id) for token in tokens]
    for tid in tenant_ids:
        sync_notion.delay(tid)
