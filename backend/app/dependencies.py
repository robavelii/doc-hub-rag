"""Request authentication.

Every authenticated request resolves to one `Principal`:

- `user`             a dashboard user with a JWT access token
- `secret_key`       a secret API key (`sk_…`, or a legacy key) used server-to-server
- `publishable_key`  a widget key (`pk_…`) that is visible in public web pages

Publishable keys can only ask questions (`get_query_tenant`). Every other
route goes through `get_current_tenant`, which rejects them, so a key copied
out of a customer's website cannot list, read, upload or delete documents or
read anyone's conversations.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db_context, get_db, set_tenant_rls
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import (
    API_KEY_KIND_PUBLISHABLE,
    api_key_needs_rehash,
    decode_token,
    hash_api_key,
    verify_api_key,
)
from app.utils.domain import is_domain_allowed

KIND_USER = "user"
KIND_SECRET_KEY = "secret_key"  # noqa: S105 - a label, not a credential
KIND_PUBLISHABLE_KEY = "publishable_key"

# Roles allowed to change the knowledge base (upload, re-ingest, delete).
DOCUMENT_WRITER_ROLES = ("owner", "admin")


@dataclass(frozen=True)
class Principal:
    tenant: Tenant
    kind: str
    user: User | None = None
    api_key_id: uuid.UUID | None = None

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user else None


async def get_current_user_optional(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    payload = decode_token(auth_header[7:])
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


@dataclass(frozen=True)
class _ResolvedKey:
    tenant: Tenant
    kind: str
    api_key_id: uuid.UUID | None


async def _resolve_api_key(api_key: str) -> _ResolvedKey | None:
    """Look up the key with a privileged session (the tenant is not known yet)."""
    prefix = api_key[:8]
    async with get_admin_db_context() as admin_db:
        key_rows = (
            await admin_db.execute(
                select(ApiKey).where(ApiKey.is_active == True, ApiKey.key_prefix == prefix)  # noqa: E712
            )
        ).scalars().all()
        for key_row in key_rows:
            if not verify_api_key(api_key, key_row.key_hash):
                continue
            tenant = await admin_db.get(Tenant, key_row.tenant_id)
            if not tenant or not tenant.is_active:
                return None
            key_row.last_used_at = datetime.now(UTC)
            if api_key_needs_rehash(key_row.key_hash):
                key_row.key_hash = hash_api_key(api_key)
            await admin_db.commit()
            kind = KIND_PUBLISHABLE_KEY if key_row.kind == API_KEY_KIND_PUBLISHABLE else KIND_SECRET_KEY
            return _ResolvedKey(tenant=tenant, kind=kind, api_key_id=key_row.id)

        # Legacy per-tenant key issued at registration: always a secret key.
        tenants = (
            await admin_db.execute(
                select(Tenant).where(Tenant.is_active == True, Tenant.api_key_prefix == prefix)  # noqa: E712
            )
        ).scalars().all()
        for tenant in tenants:
            if verify_api_key(api_key, tenant.api_key_hash):
                if api_key_needs_rehash(tenant.api_key_hash):
                    tenant.api_key_hash = hash_api_key(api_key)
                    await admin_db.commit()
                return _ResolvedKey(tenant=tenant, kind=KIND_SECRET_KEY, api_key_id=None)
    return None


async def resolve_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> Principal:
    """Authenticate the request. FastAPI caches this per request."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = decode_token(auth_header[7:])
        if not payload or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
        tenant = await db.get(Tenant, payload.get("tenant_id"))
        if not tenant or not tenant.is_active:
            raise HTTPException(status_code=401, detail="Tenant inactive or not found")
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive or not found")
        if str(user.tenant_id) != str(tenant.id):
            raise HTTPException(status_code=401, detail="Token tenant mismatch")
        request.state.tenant = tenant
        request.state.user = user
        request.state.auth_kind = KIND_USER
        await set_tenant_rls(db, str(tenant.id))
        return Principal(tenant=tenant, kind=KIND_USER, user=user)

    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        resolved = await _resolve_api_key(api_key)
        if not resolved:
            raise HTTPException(status_code=401, detail="Invalid API key")
        tenant = resolved.tenant
        # Widget keys always honour the domain allowlist. Secret keys honour it when
        # called from a browser (Origin present), which keeps existing embeds that
        # still use a legacy key protected; server-to-server calls send no Origin.
        if resolved.kind == KIND_PUBLISHABLE_KEY or request.headers.get("Origin"):
            _check_widget_domain(request, tenant)
        request.state.tenant = tenant
        request.state.auth_kind = resolved.kind
        await set_tenant_rls(db, str(tenant.id))
        return Principal(tenant=tenant, kind=resolved.kind, api_key_id=resolved.api_key_id)

    raise HTTPException(status_code=401, detail="No credentials provided")


async def get_principal(principal: Principal = Depends(resolve_principal)) -> Principal:
    """Any authenticated caller except publishable (widget) keys."""
    if principal.kind == KIND_PUBLISHABLE_KEY:
        raise HTTPException(status_code=403, detail="Widget keys can only be used to ask questions")
    return principal


async def get_current_tenant(principal: Principal = Depends(get_principal)) -> Tenant:
    return principal.tenant


async def get_query_principal(principal: Principal = Depends(resolve_principal)) -> Principal:
    """Callers allowed to ask questions: users, secret keys and publishable keys."""
    return principal


async def get_query_tenant(principal: Principal = Depends(resolve_principal)) -> Tenant:
    return principal.tenant


async def require_document_writer(principal: Principal = Depends(get_principal)) -> Tenant:
    """Upload, re-ingest and delete: owner/admin users or secret keys."""
    if principal.kind == KIND_SECRET_KEY:
        return principal.tenant
    if principal.user and principal.user.role in DOCUMENT_WRITER_ROLES:
        return principal.tenant
    raise HTTPException(status_code=403, detail="Only owners and admins can change documents")


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
