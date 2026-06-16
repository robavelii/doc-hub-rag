import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db_context, get_db, set_tenant_rls
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import decode_token, verify_api_key
from app.utils.domain import is_domain_allowed


async def get_current_user_optional(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id:
        return None
    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        return None
    if tenant_id and str(user.tenant_id) != str(tenant_id):
        return None
    request.state.user = user
    return user


def _check_widget_domain(request: Request, tenant: Tenant) -> None:
    allowed = (tenant.widget_config or {}).get("allowed_domains", [])
    if not allowed:
        return
    origin = request.headers.get("Origin") or request.headers.get("Referer", "")
    if not origin:
        raise HTTPException(status_code=403, detail="Origin header required for widget API access")
    if not is_domain_allowed(origin, allowed):
        raise HTTPException(status_code=403, detail="Domain not allowed")


async def _resolve_api_key_tenant(api_key: str) -> Tenant | None:
    """Look up tenant by API key using privileged session (cross-tenant bootstrap)."""
    prefix = api_key[:8]
    async with get_admin_db_context() as admin_db:
        key_result = await admin_db.execute(
            select(ApiKey).where(ApiKey.is_active == True, ApiKey.key_prefix == prefix)  # noqa: E712
        )
        for key_row in key_result.scalars().all():
            if verify_api_key(api_key, key_row.key_hash):
                tenant = await admin_db.get(Tenant, key_row.tenant_id)
                if tenant and tenant.is_active:
                    return tenant

        result = await admin_db.execute(
            select(Tenant).where(Tenant.is_active == True, Tenant.api_key_prefix == prefix)  # noqa: E712
        )
        for tenant in result.scalars().all():
            if verify_api_key(api_key, tenant.api_key_hash):
                return tenant
    return None


async def get_current_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> Tenant:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
        tenant_id = payload.get("tenant_id")
        tenant = await db.get(Tenant, tenant_id)
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="Tenant inactive or not found")
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive or not found")
        if str(user.tenant_id) != str(tenant.id):
            raise HTTPException(status_code=401, detail="Token tenant mismatch")
        request.state.tenant = tenant
        request.state.user = user
        await set_tenant_rls(db, str(tenant.id))
        return tenant

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        tenant = await _resolve_api_key_tenant(api_key)
        if not tenant:
            raise HTTPException(status_code=401, detail="Invalid API key")

        _check_widget_domain(request, tenant)
        request.state.tenant = tenant
        await set_tenant_rls(db, str(tenant.id))

        # Update last_used_at on the matching key row (privileged lookup, tenant-scoped write)
        prefix = api_key[:8]
        key_result = await db.execute(
            select(ApiKey).where(ApiKey.is_active == True, ApiKey.key_prefix == prefix)  # noqa: E712
        )
        for key_row in key_result.scalars().all():
            if verify_api_key(api_key, key_row.key_hash):
                key_row.last_used_at = datetime.now(timezone.utc)
                await db.commit()
                break

        return tenant

    raise HTTPException(status_code=401, detail="No credentials provided")


async def require_owner(
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    user = getattr(request.state, "user", None)
    if not user or user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    return tenant


async def require_superadmin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_current_user_optional(request, db)
    if not user or not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
