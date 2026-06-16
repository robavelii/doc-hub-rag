"""Seed demo tenants and superadmin user."""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, get_admin_db_context, set_tenant_rls
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import (
    api_key_prefix,
    generate_api_key,
    hash_api_key,
    hash_password,
    slugify,
)
from app.workers.ingest_task import ingest_notion_page

DEMO_EMAILS = {"demo@acme.com", "demo@globex.com"}

DEMO_DOCS = {
    "acme": [
        ("acme-support.txt", "Acme Corp offers 24/7 customer support. Our refund policy allows returns within 30 days."),
        ("acme-pricing.txt", "Acme pricing: Free plan includes 100MB storage. Pro plan includes 10GB and priority support."),
    ],
    "globex": [
        ("globex-api.txt", "Globex API uses REST endpoints. Authentication requires an API key in the X-API-Key header."),
        ("globex-limits.txt", "Globex rate limits: Free tier 10 req/min, Pro tier 300 req/min."),
    ],
}


def ingest_sync(doc_id: str, tenant_id: str, content: str, filename: str) -> None:
    """Run ingestion synchronously — no Celery worker required for seeding."""
    ingest_notion_page.apply(args=[doc_id, tenant_id, content, filename])
    print(f"  Ingested: {filename}")


async def reingest_pending_demo_docs() -> None:
    """Re-ingest any demo docs still pending/failed (e.g. after seed without Celery).

    Uses a privileged session: the seed session's RLS context only covers the
    last tenant it touched (or none), which would hide other tenants' docs.
    """
    async with get_admin_db_context() as db:
        result = await db.execute(
            select(Document, User.email)
            .join(User, User.tenant_id == Document.tenant_id)
            .where(User.email.in_(DEMO_EMAILS))
            .where(Document.status.in_(["pending", "failed"]))
        )
        rows = result.all()
    if not rows:
        return

    print(f"Re-ingesting {len(rows)} pending/failed demo document(s)...")
    for doc, email in rows:
        slug_base = "acme" if "acme" in email else "globex"
        content = None
        for fname, text in DEMO_DOCS[slug_base]:
            if fname == doc.filename:
                content = text
                break
        if content is None:
            continue
        ingest_sync(str(doc.id), str(doc.tenant_id), content, doc.filename)


async def seed():
    async with AsyncSessionLocal() as db:
        admin_result = await db.execute(select(User).where(User.email == settings.SUPERADMIN_EMAIL))
        if not admin_result.scalar_one_or_none():
            raw_key = generate_api_key()
            admin_tenant = Tenant(
                name="Platform Admin",
                slug="platform-admin",
                plan="pro",
                api_key_hash=hash_api_key(raw_key),
                api_key_prefix=api_key_prefix(raw_key),
            )
            db.add(admin_tenant)
            await db.flush()
            await set_tenant_rls(db, str(admin_tenant.id))
            admin_user = User(
                tenant_id=admin_tenant.id,
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                role="owner",
                is_superadmin=True,
            )
            db.add(admin_user)
            print(f"Created superadmin: {settings.SUPERADMIN_EMAIL}")

        demos = [
            ("Acme Corp", "acme", "demo@acme.com", "demo12345678"),
            ("Globex Inc", "globex", "demo@globex.com", "demo12345678"),
        ]

        for name, slug_base, email, password in demos:
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                continue

            raw_key = generate_api_key()
            tenant = Tenant(
                name=name,
                slug=slugify(slug_base),
                plan="starter",
                api_key_hash=hash_api_key(raw_key),
                api_key_prefix=api_key_prefix(raw_key),
                widget_config={
                    "primary_color": "#1D9E75" if slug_base == "acme" else "#0066CC",
                    "welcome_message": f"Hi! I'm the {name} assistant.",
                    "allowed_domains": [],
                },
            )
            db.add(tenant)
            await db.flush()
            await set_tenant_rls(db, str(tenant.id))

            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(password),
                role="owner",
            )
            db.add(user)

            for filename, content in DEMO_DOCS[slug_base]:
                doc_id = uuid.uuid4()
                doc = Document(
                    id=doc_id,
                    tenant_id=tenant.id,
                    filename=filename,
                    file_type="txt",
                    s3_key="",
                    status="pending",
                    metadata_={"seeded": True},
                )
                db.add(doc)
                await db.flush()
                ingest_sync(str(doc_id), str(tenant.id), content, filename)

            print(f"Created demo tenant: {name} ({email})")

        await db.commit()

    # Re-ingest any docs left pending from a prior seed run without Celery
    await reingest_pending_demo_docs()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
