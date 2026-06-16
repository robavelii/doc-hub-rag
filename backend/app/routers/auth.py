import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db_context, get_db, set_tenant_rls
from app.dependencies import get_current_tenant, require_owner
from app.middleware.rate_limiter import enforce_email_rate_limit, enforce_ip_rate_limit
from app.models.api_key import ApiKey
from app.models.email_verification_token import EmailVerificationToken
from app.models.invite_token import InviteToken
from app.models.password_reset_token import PasswordResetToken
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.auth_service import (
    api_key_prefix,
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_opaque_token,
    hash_password,
    issue_refresh_token,
    revoke_user_refresh_tokens,
    rotate_refresh_token,
    slugify,
    validate_password_strength,
    verify_password,
)
from app.services.billing_service import ensure_stripe_customer
from app.services.email_service import send_email

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    tenant_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class AcceptInviteRequest(BaseModel):
    token: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None


class TeamRoleUpdate(BaseModel):
    role: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _issue_auth_response(db: AsyncSession, user: User, tenant: Tenant) -> dict:
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "role": user.role,
            "is_superadmin": user.is_superadmin,
        }
    )
    refresh_token = await issue_refresh_token(db, user.id)
    await db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "tenant": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug},
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "is_superadmin": user.is_superadmin,
            "display_name": getattr(user, "display_name", None),
            "email_verified": getattr(user, "email_verified", True),
        },
    }


async def _send_verification_email(db: AsyncSession, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_opaque_token(raw_token)
    row = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(row)
    await db.flush()
    await send_email(
        user.email,
        "Verify your email",
        f"Use this token to verify your email: {raw_token}",
    )
    return raw_token


@router.post("/register")
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request)
    await enforce_email_rate_limit("register", body.email)
    validate_password_strength(body.password)

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    raw_api_key = generate_api_key()
    tenant = Tenant(
        name=body.tenant_name,
        slug=slugify(body.tenant_name),
        api_key_hash=hash_api_key(raw_api_key),
        api_key_prefix=api_key_prefix(raw_api_key),
    )
    db.add(tenant)
    await db.flush()
    await set_tenant_rls(db, str(tenant.id))

    user = User(
        tenant_id=tenant.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="owner",
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    api_key_row = ApiKey(
        tenant_id=tenant.id,
        name="Default",
        key_prefix=api_key_prefix(raw_api_key),
        key_hash=hash_api_key(raw_api_key),
    )
    db.add(api_key_row)

    try:
        await ensure_stripe_customer(tenant, body.email, db)
    except Exception:
        pass

    verify_token = await _send_verification_email(db, user)
    response = await _issue_auth_response(db, user, tenant)
    response["api_key"] = raw_api_key
    response["verification_token"] = verify_token
    await log_audit(db, "user_registered", tenant_id=str(tenant.id), user_id=str(user.id), ip_address=_client_ip(request))
    return response


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request)
    await enforce_email_rate_limit("login", body.email)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        await log_audit(db, "login_failed", details={"email": body.email}, ip_address=_client_ip(request))
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")

    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Account suspended")

    response = await _issue_auth_response(db, user, tenant)
    await log_audit(db, "login", tenant_id=str(tenant.id), user_id=str(user.id), ip_address=_client_ip(request))
    return response


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request, limit=30)
    new_refresh, user_id = await rotate_refresh_token(db, body.refresh_token)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Account suspended")

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "role": user.role,
            "is_superadmin": user.is_superadmin,
        }
    )
    await db.commit()
    return {"access_token": access_token, "refresh_token": new_refresh}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request)
    await enforce_email_rate_limit("forgot", body.email, limit=5)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        raw_token = secrets.token_urlsafe(32)
        row = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(row)
        await db.commit()
        await send_email(
            user.email,
            "Password reset",
            f"Use this token to reset your password: {raw_token}",
        )
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request)
    validate_password_strength(body.new_password)

    token_hash = hash_opaque_token(body.token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")

    user.password_hash = hash_password(body.new_password)
    row.used_at = datetime.now(timezone.utc)
    await revoke_user_refresh_tokens(db, user.id)
    await db.commit()
    await log_audit(db, "password_reset", tenant_id=str(user.tenant_id), user_id=str(user.id), ip_address=_client_ip(request))
    return {"ok": True}


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_opaque_token(body.token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.verified_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")

    user.email_verified = True
    row.verified_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/invite")
async def invite_member(
    body: InviteRequest,
    request: Request,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invite = InviteToken(
        tenant_id=tenant.id,
        email=body.email,
        role=body.role,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await send_email(body.email, "Team invitation", f"Accept invite with token: {raw_token}")
    actor = getattr(request.state, "user", None)
    await log_audit(db, "invite_sent", tenant_id=str(tenant.id), user_id=str(actor.id) if actor else None, details={"email": body.email})
    return {"email": body.email, "expires_in_days": 7}


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_ip_rate_limit("auth", request)
    validate_password_strength(body.password)

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    async with get_admin_db_context() as admin_db:
        result = await admin_db.execute(select(InviteToken).where(InviteToken.token_hash == token_hash))
        invite = result.scalar_one_or_none()
    if not invite or invite.accepted_at:
        raise HTTPException(status_code=400, detail="Invalid invite")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite expired")

    await set_tenant_rls(db, str(invite.tenant_id))

    existing = await db.execute(select(User).where(User.email == invite.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        tenant_id=invite.tenant_id,
        email=invite.email,
        password_hash=hash_password(body.password),
        role=invite.role,
        email_verified=True,
    )
    db.add(user)
    invite.accepted_at = datetime.now(timezone.utc)
    await db.flush()

    tenant = await db.get(Tenant, invite.tenant_id)
    response = await _issue_auth_response(db, user, tenant)
    await log_audit(db, "invite_accepted", tenant_id=str(tenant.id), user_id=str(user.id), ip_address=_client_ip(request))
    return response


@router.get("/team")
async def list_team(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.tenant_id == tenant.id, User.is_active == True))  # noqa: E712
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "display_name": getattr(u, "display_name", None),
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.delete("/team/{user_id}")
async def remove_team_member(
    user_id: str,
    request: Request,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, uuid.UUID(user_id))
    if not user or str(user.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove owner")
    user.is_active = False
    await revoke_user_refresh_tokens(db, user.id)
    await db.commit()
    actor = getattr(request.state, "user", None)
    await log_audit(db, "team_member_removed", tenant_id=str(tenant.id), user_id=str(actor.id) if actor else None)
    return {"ok": True}


@router.patch("/team/{user_id}")
async def update_team_role(
    user_id: str,
    body: TeamRoleUpdate,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    user = await db.get(User, uuid.UUID(user_id))
    if not user or str(user.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot change owner role")
    user.role = body.role
    await db.commit()
    return {"id": str(user.id), "role": user.role}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    user: User | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    validate_password_strength(body.new_password)
    user.password_hash = hash_password(body.new_password)
    await revoke_user_refresh_tokens(db, user.id)
    await db.commit()
    await log_audit(db, "password_changed", tenant_id=str(tenant.id), user_id=str(user.id))
    return {"ok": True}


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    user: User | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None and body.email != user.email:
        existing = await db.execute(
            select(User).where(User.email == body.email, User.tenant_id == tenant.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = body.email
        user.email_verified = False
        await _send_verification_email(db, user)
    await db.commit()
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": getattr(user, "display_name", None),
        "role": user.role,
        "email_verified": getattr(user, "email_verified", True),
    }
