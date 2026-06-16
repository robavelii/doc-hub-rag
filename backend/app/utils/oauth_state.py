import hashlib
import hmac
import secrets

from app.config import settings


def sign_oauth_state(tenant_id: str) -> str:
    nonce = secrets.token_hex(16)
    payload = f"{tenant_id}:{nonce}"
    signature = hmac.new(
        settings.JWT_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_oauth_state(state: str) -> str | None:
    parts = state.split(":")
    if len(parts) != 3:
        return None
    tenant_id, nonce, signature = parts
    payload = f"{tenant_id}:{nonce}"
    expected = hmac.new(
        settings.JWT_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return tenant_id
