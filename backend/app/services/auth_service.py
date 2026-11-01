import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken

MIN_PASSWORD_LENGTH = 12
# bcrypt only uses the first 72 bytes and bcrypt>=5 raises on longer input.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    raw = plain.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(raw, hashed.encode())


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes",
        )


API_KEY_KIND_SECRET = "secret"  # noqa: S105 - a label, not a credential
API_KEY_KIND_PUBLISHABLE = "publishable"
_API_KEY_PREFIXES = {API_KEY_KIND_SECRET: "sk_", API_KEY_KIND_PUBLISHABLE: "pk_"}
_SHA256_SCHEME = "sha256$"


def generate_api_key(kind: str = API_KEY_KIND_SECRET) -> str:
    """256-bit random key. `pk_` keys are safe to embed in web pages; `sk_` keys are not."""
    return _API_KEY_PREFIXES[kind] + secrets.token_hex(32)


def hash_api_key(raw_key: str) -> str:
    """API keys carry 256 bits of entropy, so a fast hash is safe and avoids bcrypt per request."""
    return _SHA256_SCHEME + hashlib.sha256(raw_key.encode()).hexdigest()


def api_key_prefix(raw_key: str) -> str:
    return raw_key[:8]


def verify_api_key(raw_key: str, hashed: str) -> bool:
    if hashed.startswith(_SHA256_SCHEME):
        return hmac.compare_digest(hash_api_key(raw_key), hashed)
    # Legacy bcrypt hashes from before 2026-11; upgraded on next successful use.
    try:
        return bcrypt.checkpw(raw_key.encode(), hashed.encode())
    except ValueError:
        return False


def api_key_needs_rehash(hashed: str) -> bool:
    return not hashed.startswith(_SHA256_SCHEME)


def hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload["type"] = "access"
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def slugify(name: str) -> str:
    base = name.lower().strip().replace(" ", "-")
    suffix = uuid.uuid4().hex[:6]
    return f"{base}-{suffix}"


async def issue_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    raw_token = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    db.add(row)
    await db.flush()
    return raw_token


async def revoke_user_refresh_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    for row in result.scalars().all():
        row.revoked_at = now


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[str, uuid.UUID]:
    token_hash = hash_opaque_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row or row.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    row.revoked_at = datetime.now(UTC)
    new_token = await issue_refresh_token(db, row.user_id)
    await db.flush()
    return new_token, row.user_id
