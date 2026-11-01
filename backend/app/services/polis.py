"""Client for a self-hosted Ory Polis (formerly BoxyHQ SAML Jackson).

Each Doc-Hub tenant maps to one Polis (tenant, product) pair:
tenant = our tenant UUID, product = settings.POLIS_PRODUCT.

- SSO: SAML or OIDC connections to the customer's IdP. Polis exposes them to us
  as a standard OAuth 2.0 authorization-code flow.
- Directory sync: a SCIM 2.0 endpoint per tenant; Polis posts signed webhook
  events (users, groups, memberships) to /webhooks/polis/dsync.
"""

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

TIMEOUT = httpx.Timeout(15.0)
SIGNATURE_TOLERANCE_SECONDS = 300


class PolisError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _client() -> httpx.AsyncClient:
    if not settings.sso_enabled:
        raise PolisError("SSO is not configured on this server", 503)
    return httpx.AsyncClient(base_url=settings.POLIS_URL.rstrip("/"), timeout=TIMEOUT)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Api-Key {settings.POLIS_API_KEY}"}


def _raise_for(response: httpx.Response, action: str) -> None:
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message") or response.text
        except ValueError:
            detail = response.text
        status = 400 if response.status_code in (400, 422) else 502
        raise PolisError(f"{action} failed: {detail[:300]}", status)


def tenant_key(tenant_id) -> dict[str, str]:
    return {"tenant": str(tenant_id), "product": settings.POLIS_PRODUCT}


def callback_url() -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}/auth/sso/callback"


def scim_webhook_url() -> str:
    return f"{settings.APP_BASE_URL.rstrip('/')}/webhooks/polis/dsync"


# --- connections -------------------------------------------------------------------


async def list_connections(tenant_id) -> list[dict]:
    async with _client() as client:
        r = await client.get("/api/v1/sso", params=tenant_key(tenant_id), headers=_admin_headers())
    _raise_for(r, "Listing SSO connections")
    return r.json() or []


async def create_connection(tenant_id, params: dict[str, Any]) -> dict:
    """params: {"metadataUrl"} or {"rawMetadata"} (SAML), or
    {"oidcDiscoveryUrl", "oidcClientId", "oidcClientSecret"} (OIDC)."""
    body = {
        **tenant_key(tenant_id),
        "name": params.pop("name", "Company SSO"),
        "defaultRedirectUrl": callback_url(),
        "redirectUrl": [callback_url()],
        **params,
    }
    async with _client() as client:
        r = await client.post("/api/v1/sso", json=body, headers=_admin_headers())
    _raise_for(r, "Creating the SSO connection")
    return r.json()


async def delete_connections(tenant_id) -> None:
    async with _client() as client:
        r = await client.delete("/api/v1/sso", params=tenant_key(tenant_id), headers=_admin_headers())
    _raise_for(r, "Deleting the SSO connection")


# --- OAuth login ---------------------------------------------------------------------


def authorize_url(tenant_id, state: str) -> str:
    base = (settings.POLIS_PUBLIC_URL or settings.POLIS_URL).rstrip("/")
    query = {
        "response_type": "code",
        "client_id": "dummy",
        "redirect_uri": callback_url(),
        "state": state,
        **tenant_key(tenant_id),
    }
    return f"{base}/api/oauth/authorize?{urlencode(query)}"


async def exchange_code(code: str) -> dict:
    """Returns the user profile: {id, email, firstName, lastName, requested: {tenant, product}, ...}."""
    async with _client() as client:
        token = await client.post(
            "/api/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "dummy",
                "client_secret": settings.POLIS_CLIENT_SECRET_VERIFIER,
                "code": code,
                "redirect_uri": callback_url(),
            },
        )
        _raise_for(token, "SSO token exchange")
        access_token = token.json().get("access_token")
        if not access_token:
            raise PolisError("SSO token exchange returned no access token")
        profile = await client.get("/api/oauth/userinfo", headers={"Authorization": f"Bearer {access_token}"})
    _raise_for(profile, "Reading the SSO profile")
    return profile.json()


# --- directory sync (SCIM) -------------------------------------------------------------


async def get_directory(tenant_id) -> dict | None:
    async with _client() as client:
        r = await client.get("/api/v1/dsync", params=tenant_key(tenant_id), headers=_admin_headers())
    _raise_for(r, "Reading the directory")
    data = r.json().get("data") or []
    return data[0] if data else None


async def create_directory(tenant_id, directory_type: str, name: str) -> dict:
    body = {
        **tenant_key(tenant_id),
        "name": name,
        "type": directory_type,
        "webhook_url": scim_webhook_url(),
        "webhook_secret": settings.POLIS_WEBHOOK_SECRET,
    }
    async with _client() as client:
        r = await client.post("/api/v1/dsync", json=body, headers=_admin_headers())
    _raise_for(r, "Creating the directory")
    return r.json().get("data") or {}


def verify_webhook_signature(raw_body: bytes, header: str | None, *, now: float | None = None) -> bool:
    """Header format: "t=<unix ms>,s=<hex HMAC-SHA256(secret, f'{t}.{body}')>"."""
    if not header or not settings.POLIS_WEBHOOK_SECRET:
        return False
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp, signature = parts["t"], parts["s"]
        age = abs((now if now is not None else time.time()) - int(timestamp) / 1000)
    except (KeyError, ValueError):
        return False
    if age > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(
        settings.POLIS_WEBHOOK_SECRET.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
