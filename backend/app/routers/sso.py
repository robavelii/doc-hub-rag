"""Enterprise SSO (SAML/OIDC) and SCIM provisioning through Ory Polis.

Login:  GET /auth/sso/start?email=… → IdP → GET /auth/sso/callback → dashboard
Admin:  /sso/config, /sso/connection, /sso/domains, /sso/directory   (owner/admin)
SCIM:   POST /webhooks/polis/dsync   (signed by Polis)
"""

import json
import logging
import re
import secrets
import uuid
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_admin_db_context, get_db, set_tenant_rls
from app.dependencies import require_owner
from app.middleware.rate_limiter import enforce_ip_rate_limit
from app.models.access import Group, GroupMember
from app.models.sso_domain import SsoDomain
from app.models.tenant import Tenant
from app.models.user import User
from app.services import polis
from app.services.audit_service import log_audit
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sso"])

STATE_TTL_SECONDS = 600
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
# Consumer mailbox domains cannot be claimed: they are not owned by any one customer.
PUBLIC_EMAIL_DOMAINS = frozenset(
    {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com", "proton.me", "protonmail.com", "aol.com"}
)

async def _state_store():
    from app.services.cache_service import get_redis

    return await get_redis()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip() if "@" in email else ""


def _polis_error(exc: polis.PolisError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


async def _tenant_for_domain(domain: str) -> uuid.UUID | None:
    async with get_admin_db_context() as admin_db:
        row = await admin_db.get(SsoDomain, domain)
        return row.tenant_id if row else None


# --- login -----------------------------------------------------------------------------


@router.get("/auth/sso/discover")
async def discover(email: str, request: Request):
    """Does this email's company use SSO? Reveals nothing about the tenant."""
    await enforce_ip_rate_limit("auth", request)
    tenant_id = await _tenant_for_domain(_email_domain(email)) if settings.sso_enabled else None
    return {"sso": tenant_id is not None}


@router.get("/auth/sso/start")
async def start(email: str, request: Request):
    await enforce_ip_rate_limit("auth", request)
    if not settings.sso_enabled:
        raise HTTPException(status_code=503, detail="SSO is not configured on this server")
    tenant_id = await _tenant_for_domain(_email_domain(email))
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No SSO connection for this email domain")
    state = secrets.token_urlsafe(32)
    store = await _state_store()
    await store.setex(f"sso:state:{state}", STATE_TTL_SECONDS, json.dumps({"tenant_id": str(tenant_id)}))
    return RedirectResponse(polis.authorize_url(tenant_id, state), status_code=302)


def _dashboard_redirect(**params) -> RedirectResponse:
    # Tokens travel in the URL fragment: never sent to servers or written to access logs.
    return RedirectResponse(f"{settings.DASHBOARD_URL.rstrip('/')}/sso/callback#{urlencode(params)}", status_code=302)


async def _find_or_create_sso_user(db: AsyncSession, tenant: Tenant, profile: dict) -> User:
    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Your identity provider did not send an email address")
    claimed = (
        await db.execute(select(SsoDomain.domain).where(SsoDomain.tenant_id == tenant.id))
    ).scalars().all()
    if _email_domain(email) not in claimed:
        raise HTTPException(status_code=403, detail="This email domain is not linked to your organization's SSO")

    user = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if user is not None:
        if user.tenant_id != tenant.id:
            # Emails are globally unique logins today; never attach an SSO login to another tenant's account.
            raise HTTPException(status_code=409, detail="This email already belongs to another workspace")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account deactivated")
        return user

    name = " ".join(p for p in (profile.get("firstName"), profile.get("lastName")) if p) or None
    user = User(
        tenant_id=tenant.id,
        email=email,
        display_name=name,
        password_hash=hash_password(secrets.token_urlsafe(48)),  # unusable: SSO users sign in through the IdP
        role="member",
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@router.get("/auth/sso/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    from app.routers.auth import issue_auth_response

    if error or not code or not state:
        return _dashboard_redirect(error=error or "sso_failed")
    store = await _state_store()
    raw = await store.getdel(f"sso:state:{state}")
    if not raw:
        return _dashboard_redirect(error="sso_expired")
    tenant_id = json.loads(raw)["tenant_id"]

    try:
        profile = await polis.exchange_code(code)
    except polis.PolisError as exc:
        logger.warning("SSO code exchange failed: %s", exc)
        return _dashboard_redirect(error="sso_failed")
    requested = profile.get("requested") or {}
    if requested.get("tenant") != tenant_id or requested.get("product") != settings.POLIS_PRODUCT:
        logger.warning("SSO profile tenant mismatch: state=%s profile=%s", tenant_id, requested)
        return _dashboard_redirect(error="sso_failed")

    async with get_admin_db_context() as db:
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        if not tenant or not tenant.is_active:
            return _dashboard_redirect(error="account_suspended")
        await set_tenant_rls(db, tenant_id)
        try:
            user = await _find_or_create_sso_user(db, tenant, profile)
        except HTTPException as exc:
            return _dashboard_redirect(error=exc.detail)
        response = await issue_auth_response(db, user, tenant)
        await log_audit(db, "login_sso", tenant_id=tenant_id, user_id=str(user.id))
    return _dashboard_redirect(access_token=response["access_token"], refresh_token=response["refresh_token"])


# --- admin configuration --------------------------------------------------------------------


class ConnectionRequest(BaseModel):
    metadata_url: str | None = None
    raw_metadata: str | None = Field(default=None, max_length=200_000)
    oidc_discovery_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None

    @model_validator(mode="after")
    def _one_kind(self):
        saml = bool(self.metadata_url or self.raw_metadata)
        oidc = bool(self.oidc_discovery_url and self.oidc_client_id and self.oidc_client_secret)
        if saml == oidc:
            raise ValueError("Provide SAML metadata (URL or XML) or OIDC discovery URL + client id + secret")
        return self


class DomainsRequest(BaseModel):
    domains: list[str] = Field(max_length=20)
    enforced: bool = False


class DirectoryRequest(BaseModel):
    type: Literal["okta-scim-v2", "azure-scim-v2", "onelogin-scim-v2", "jumpcloud-scim-v2", "generic-scim-v2"]


@router.get("/sso/config")
async def get_config(tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    domains = await _domains(tenant)
    out = {
        "available": settings.sso_enabled,
        "domains": domains,
        "enforced": tenant.sso_enforced,
        "callback_url": polis.callback_url(),
        "connections": [],
        "directory": None,
    }
    if settings.sso_enabled:
        try:
            out["connections"] = [
                {"name": c.get("name"), "type": "oidc" if c.get("oidcProvider") else "saml"}
                for c in await polis.list_connections(tenant.id)
            ]
            directory = await polis.get_directory(tenant.id)
            out["directory"] = {"type": directory["type"], "scim_endpoint": directory["scim"].get("endpoint")} if directory else None
        except polis.PolisError as exc:
            raise _polis_error(exc) from exc
    return out


async def _domains(tenant: Tenant) -> list[str]:
    async with get_admin_db_context() as admin_db:
        rows = await admin_db.execute(select(SsoDomain.domain).where(SsoDomain.tenant_id == tenant.id))
        return sorted(rows.scalars().all())


@router.post("/sso/connection")
async def create_connection(
    body: ConnectionRequest, request: Request, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    params = (
        {"metadataUrl": body.metadata_url} if body.metadata_url
        else {"rawMetadata": body.raw_metadata} if body.raw_metadata
        else {
            "oidcDiscoveryUrl": body.oidc_discovery_url,
            "oidcClientId": body.oidc_client_id,
            "oidcClientSecret": body.oidc_client_secret,
        }
    )
    try:
        await polis.create_connection(tenant.id, params)
    except polis.PolisError as exc:
        raise _polis_error(exc) from exc
    user = getattr(request.state, "user", None)
    await log_audit(db, "sso_connection_created", tenant_id=str(tenant.id), user_id=str(user.id) if user else None)
    return {"ok": True}


@router.delete("/sso/connection")
async def delete_connection(request: Request, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    try:
        await polis.delete_connections(tenant.id)
    except polis.PolisError as exc:
        raise _polis_error(exc) from exc
    tenant.sso_enforced = False  # never leave users locked out of a tenant with no IdP
    await db.merge(tenant)
    await db.commit()
    user = getattr(request.state, "user", None)
    await log_audit(db, "sso_connection_deleted", tenant_id=str(tenant.id), user_id=str(user.id) if user else None)
    return {"ok": True}


@router.put("/sso/domains")
async def set_domains(
    body: DomainsRequest, request: Request, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    domains = sorted({d.lower().strip().lstrip("@") for d in body.domains if d.strip()})
    for domain in domains:
        if not DOMAIN_RE.match(domain):
            raise HTTPException(status_code=422, detail=f"Invalid domain: {domain}")
        if domain in PUBLIC_EMAIL_DOMAINS:
            raise HTTPException(status_code=422, detail=f"{domain} is a public email provider and cannot be claimed")
    user = getattr(request.state, "user", None)
    if body.enforced and user is not None and _email_domain(user.email) not in domains and user.role != "owner":
        raise HTTPException(status_code=422, detail="Enforcing SSO would lock you out: add your own domain first")

    async with get_admin_db_context() as admin_db:
        taken = (
            await admin_db.execute(
                select(SsoDomain.domain).where(SsoDomain.domain.in_(domains), SsoDomain.tenant_id != tenant.id)
            )
        ).scalars().all()
        if taken:
            raise HTTPException(status_code=409, detail=f"Already claimed by another workspace: {', '.join(taken)}")
        await admin_db.execute(delete(SsoDomain).where(SsoDomain.tenant_id == tenant.id))
        for domain in domains:
            admin_db.add(SsoDomain.new(domain, tenant.id))
        row = await admin_db.get(Tenant, tenant.id)
        row.sso_enforced = body.enforced and bool(domains)
        await admin_db.commit()
    await log_audit(
        db, "sso_domains_updated", tenant_id=str(tenant.id), user_id=str(user.id) if user else None,
        details={"domains": domains, "enforced": body.enforced},
    )
    return {"domains": domains, "enforced": body.enforced and bool(domains)}


@router.post("/sso/directory")
async def create_directory(
    body: DirectoryRequest, request: Request, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    """Returns the SCIM endpoint + bearer token to paste into the IdP. The token is shown once."""
    if not settings.POLIS_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Directory sync is not configured on this server")
    try:
        if await polis.get_directory(tenant.id):
            raise HTTPException(status_code=409, detail="A directory is already connected")
        directory = await polis.create_directory(tenant.id, body.type, f"{tenant.name} directory")
    except polis.PolisError as exc:
        raise _polis_error(exc) from exc
    user = getattr(request.state, "user", None)
    await log_audit(db, "scim_directory_created", tenant_id=str(tenant.id), user_id=str(user.id) if user else None)
    scim = directory.get("scim") or {}
    return {"scim_endpoint": scim.get("endpoint"), "scim_token": scim.get("secret"), "type": directory.get("type")}


# --- SCIM webhook ----------------------------------------------------------------------------


async def _apply_event(db: AsyncSession, tenant: Tenant, event: str, data: dict) -> None:
    if event in ("user.created", "user.updated", "user.deleted"):
        email = (data.get("email") or "").strip().lower()
        if not email:
            return
        user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
        if user is not None and user.tenant_id != tenant.id:
            logger.warning("SCIM user %s belongs to another tenant; ignored", email)
            return
        active = event != "user.deleted" and data.get("active", True) is not False
        if user is None:
            if not active:
                return
            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(48)),
                role="member",
                email_verified=True,
            )
            db.add(user)
        name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        if name:
            user.display_name = name
        if user.role != "owner":  # never let the IdP deactivate the workspace owner
            user.is_active = active
        return

    group_data = data.get("group") if event.startswith("group.user_") else data
    external_id = str((group_data or {}).get("id") or "")
    if not external_id:
        return
    group = (
        await db.execute(select(Group).where(Group.tenant_id == tenant.id, Group.external_id == external_id))
    ).scalar_one_or_none()

    if event in ("group.created", "group.updated"):
        name = (data.get("name") or external_id)[:120]
        if group is None:
            clash = (await db.execute(select(Group).where(Group.tenant_id == tenant.id, Group.name == name))).scalar_one_or_none()
            group = Group(tenant_id=tenant.id, source="scim", external_id=external_id, name=name if clash is None else f"{name} (SCIM)")
            db.add(group)
        else:
            group.name = name
    elif event == "group.deleted":
        if group is not None:
            await db.delete(group)
    elif event in ("group.user_added", "group.user_removed") and group is not None:
        email = (data.get("email") or "").strip().lower()
        user = (
            await db.execute(select(User).where(User.tenant_id == tenant.id, func.lower(User.email) == email))
        ).scalar_one_or_none()
        if user is None:
            return
        await db.flush()
        existing = await db.get(GroupMember, (group.id, user.id))
        if event == "group.user_added" and existing is None:
            db.add(GroupMember(group_id=group.id, user_id=user.id, tenant_id=tenant.id))
        elif event == "group.user_removed" and existing is not None:
            await db.delete(existing)


@router.post("/webhooks/polis/dsync")
async def directory_webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("Ory-Polis-Signature") or request.headers.get("BoxyHQ-Signature")
    if not polis.verify_webhook_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = json.loads(raw)
    events = payload if isinstance(payload, list) else [payload]

    applied = 0
    for event in events:
        if event.get("product") != settings.POLIS_PRODUCT:
            continue
        try:
            tenant_uuid = uuid.UUID(str(event.get("tenant")))
        except ValueError:
            continue
        async with get_admin_db_context() as db:
            tenant = await db.get(Tenant, tenant_uuid)
            if tenant is None:
                continue
            await set_tenant_rls(db, str(tenant.id))
            await _apply_event(db, tenant, str(event.get("event")), event.get("data") or {})
            await db.commit()
            applied += 1
    return {"applied": applied}
