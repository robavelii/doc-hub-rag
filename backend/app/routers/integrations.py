import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, set_tenant_rls
from app.dependencies import get_current_tenant, require_owner
from app.models.integration_token import IntegrationToken
from app.models.tenant import Tenant
from app.services.encryption_service import encrypt_value
from app.utils.oauth_state import sign_oauth_state, verify_oauth_state
from app.workers.sync_task import sync_notion

router = APIRouter(prefix="/integrations", tags=["integrations"])

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"


@router.get("/notion/connect")
async def notion_connect(tenant: Tenant = Depends(require_owner)):
    if not settings.NOTION_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Notion integration not configured")
    params = {
        "client_id": settings.NOTION_CLIENT_ID,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": f"{settings.APP_BASE_URL}/integrations/notion/callback",
        "state": sign_oauth_state(str(tenant.id)),
    }
    return RedirectResponse(NOTION_AUTH_URL + "?" + urllib.parse.urlencode(params))


@router.get("/notion/callback")
async def notion_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    if not settings.NOTION_CLIENT_ID or not settings.NOTION_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Notion integration not configured")

    tenant_id = verify_oauth_state(state)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            NOTION_TOKEN_URL,
            auth=(settings.NOTION_CLIENT_ID, settings.NOTION_CLIENT_SECRET),
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.APP_BASE_URL}/integrations/notion/callback",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Notion token")

    data = response.json()
    await set_tenant_rls(db, tenant_id)
    existing = await db.execute(
        select(IntegrationToken).where(
            IntegrationToken.tenant_id == tenant_id,
            IntegrationToken.provider == "notion",
        )
    )
    token_row = existing.scalar_one_or_none()
    if token_row:
        token_row.access_token = encrypt_value(data["access_token"])
    else:
        token_row = IntegrationToken(
            tenant_id=tenant_id,
            provider="notion",
            access_token=encrypt_value(data["access_token"]),
        )
        db.add(token_row)
    await db.commit()

    sync_notion.delay(tenant_id)
    return RedirectResponse(f"{settings.CORS_ORIGINS.split(',')[0].strip()}/integrations?connected=notion")


@router.get("/status")
async def integration_status(tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntegrationToken).where(IntegrationToken.tenant_id == tenant.id)
    )
    tokens = result.scalars().all()
    return {"connected": [t.provider for t in tokens]}
