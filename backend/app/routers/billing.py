from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_tenant, require_owner
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.services.billing_service import create_checkout_session, create_portal_session, handle_webhook_event
from app.services.usage_service import PLAN_LIMITS, get_monthly_token_usage, get_storage_usage

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str


@router.get("/subscription")
async def get_subscription(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant.id))
    sub = result.scalar_one_or_none()
    tokens_used = await get_monthly_token_usage(str(tenant.id), db)
    storage_used = await get_storage_usage(str(tenant.id), db)
    limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    return {
        "plan": tenant.plan,
        "status": sub.status if sub else "inactive",
        "stripe_customer_id": sub.stripe_customer_id if sub else None,
        "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "tokens_used": tokens_used,
        "tokens_limit": limits["tokens"],
        "storage_used_bytes": storage_used,
        "storage_limit_bytes": limits["storage"],
    }


@router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    request: Request,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    user: User | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="User required")
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    url = await create_checkout_session(tenant, user.email, body.plan, db)
    return {"checkout_url": url}


@router.post("/portal")
async def portal(
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    url = await create_portal_session(tenant, db)
    return {"portal_url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    await handle_webhook_event(payload, sig, db)
    return {"received": True}
