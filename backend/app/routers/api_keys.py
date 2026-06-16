from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant, require_owner
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.services.audit_service import log_audit
from app.services.auth_service import api_key_prefix, generate_api_key, hash_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = "Default"


@router.get("")
async def list_api_keys(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.tenant_id == tenant.id, ApiKey.is_active == True)  # noqa: E712
    )
    keys = result.scalars().all()
    if not keys and tenant.api_key_prefix:
        return [
            {
                "id": "legacy",
                "name": "Default (legacy)",
                "key_prefix": tenant.api_key_prefix,
                "masked_key": f"sk-...{tenant.api_key_prefix}",
                "last_used_at": None,
                "created_at": None,
            }
        ]
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "masked_key": f"sk-...{k.key_prefix}",
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in keys
    ]


@router.post("")
async def create_api_key(
    body: CreateApiKeyRequest,
    request: Request,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    raw_key = generate_api_key()
    key = ApiKey(
        tenant_id=tenant.id,
        name=body.name,
        key_prefix=api_key_prefix(raw_key),
        key_hash=hash_api_key(raw_key),
    )
    db.add(key)
    await db.commit()
    user = getattr(request.state, "user", None)
    await log_audit(
        db,
        "api_key_created",
        tenant_id=str(tenant.id),
        user_id=str(user.id) if user else None,
        details={"name": body.name},
    )
    return {
        "id": str(key.id),
        "name": key.name,
        "api_key": raw_key,
        "masked_key": f"sk-...{key.key_prefix}",
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    if key_id == "legacy":
        raise HTTPException(status_code=400, detail="Cannot revoke legacy key; create a new key first")
    key = await db.get(ApiKey, key_id)
    if not key or str(key.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await db.commit()
    user = getattr(request.state, "user", None)
    await log_audit(
        db,
        "api_key_revoked",
        tenant_id=str(tenant.id),
        user_id=str(user.id) if user else None,
        details={"key_id": key_id},
    )
    return {"ok": True}
