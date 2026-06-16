from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_tenant_rls
from app.dependencies import require_superadmin
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.auth_service import (
    api_key_prefix,
    generate_api_key,
    hash_api_key,
    hash_password,
    slugify,
    validate_password_strength,
)
from app.services.usage_service import (
    PLAN_LIMITS,
    get_global_token_usage_admin,
    get_monthly_token_usage_admin,
    get_storage_usage_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class TenantPatchRequest(BaseModel):
    is_active: bool | None = None
    plan: str | None = None


class TenantCreateRequest(BaseModel):
    name: str
    plan: str = "free"
    owner_email: EmailStr
    owner_password: str


@router.post("/tenants")
async def create_tenant(
    body: TenantCreateRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    validate_password_strength(body.owner_password)
    if body.plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    limits = PLAN_LIMITS[body.plan]
    raw_api_key = generate_api_key()
    tenant = Tenant(
        name=body.name,
        slug=slugify(body.name),
        plan=body.plan,
        monthly_token_limit=limits["tokens"],
        storage_limit_bytes=limits["storage"],
        api_key_hash=hash_api_key(raw_api_key),
        api_key_prefix=api_key_prefix(raw_api_key),
    )
    db.add(tenant)
    await db.flush()
    await set_tenant_rls(db, str(tenant.id))

    user = User(
        tenant_id=tenant.id,
        email=body.owner_email,
        password_hash=hash_password(body.owner_password),
        role="owner",
        email_verified=True,
    )
    db.add(user)

    api_key_row = ApiKey(
        tenant_id=tenant.id,
        name="Default",
        key_prefix=api_key_prefix(raw_api_key),
        key_hash=hash_api_key(raw_api_key),
    )
    db.add(api_key_row)
    await db.commit()

    await log_audit(
        db,
        "tenant_created",
        tenant_id=str(tenant.id),
        user_id=str(admin.id),
        details={"name": tenant.name, "plan": tenant.plan},
    )
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "api_key": raw_api_key,
        "owner_email": body.owner_email,
    }


@router.get("/tenants")
async def list_tenants(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    items = []
    for tenant in tenants:
        tokens_used = await get_monthly_token_usage_admin(str(tenant.id))
        storage_used = await get_storage_usage_admin(str(tenant.id))
        items.append(
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan,
                "is_active": tenant.is_active,
                "monthly_tokens_used": tokens_used,
                "monthly_token_limit": tenant.monthly_token_limit,
                "storage_used_bytes": storage_used,
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            }
        )
    return items


@router.get("/tenants/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tokens_used = await get_monthly_token_usage_admin(str(tenant.id))
    storage_used = await get_storage_usage_admin(str(tenant.id))
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "is_active": tenant.is_active,
        "monthly_tokens_used": tokens_used,
        "monthly_token_limit": tenant.monthly_token_limit,
        "storage_used_bytes": storage_used,
        "widget_config": tenant.widget_config,
    }


@router.patch("/tenants/{tenant_id}")
async def patch_tenant(
    tenant_id: str,
    body: TenantPatchRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if body.is_active is not None:
        tenant.is_active = body.is_active
    if body.plan is not None:
        if body.plan not in PLAN_LIMITS:
            raise HTTPException(status_code=400, detail="Invalid plan")
        limits = PLAN_LIMITS[body.plan]
        tenant.plan = body.plan
        tenant.monthly_token_limit = limits["tokens"]
        tenant.storage_limit_bytes = limits["storage"]
        await log_audit(
            db,
            "plan_changed",
            tenant_id=str(tenant.id),
            user_id=str(admin.id),
            details={"plan": body.plan, "source": "admin"},
        )
    await db.commit()
    return {"id": str(tenant.id), "is_active": tenant.is_active, "plan": tenant.plan}


@router.get("/usage/global")
async def global_usage(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    total_tokens = await get_global_token_usage_admin()
    tenant_count = await db.execute(select(func.count()).select_from(Tenant))
    return {
        "total_tokens_this_month": total_tokens,
        "total_tenants": tenant_count.scalar() or 0,
    }
