from datetime import datetime, timezone

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_admin_db_context, set_tenant_rls
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.audit_service import log_audit
from app.services.usage_service import PLAN_LIMITS

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICES = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "pro": settings.STRIPE_PRICE_PRO,
}

PRICE_TO_PLAN = {v: k for k, v in PLAN_PRICES.items() if v}


def _plan_from_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    return PRICE_TO_PLAN.get(price_id)


def _apply_plan(tenant: Tenant, plan: str) -> None:
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    tenant.plan = plan
    tenant.monthly_token_limit = limits["tokens"]
    tenant.storage_limit_bytes = limits["storage"]


async def get_or_create_subscription(tenant: Tenant, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant.id))
    sub = result.scalar_one_or_none()
    if sub:
        return sub
    sub = Subscription(tenant_id=tenant.id, status="inactive")
    db.add(sub)
    await db.flush()
    return sub


async def ensure_stripe_customer(tenant: Tenant, email: str, db: AsyncSession) -> str:
    sub = await get_or_create_subscription(tenant, db)
    if sub.stripe_customer_id:
        return sub.stripe_customer_id
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    customer = stripe.Customer.create(email=email, metadata={"tenant_id": str(tenant.id)})
    sub.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


async def create_checkout_session(tenant: Tenant, email: str, plan: str, db: AsyncSession) -> str:
    price_id = PLAN_PRICES.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan for checkout")
    customer_id = await ensure_stripe_customer(tenant, email, db)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"tenant_id": str(tenant.id), "plan": plan},
    )
    return session.url


async def create_portal_session(tenant: Tenant, db: AsyncSession) -> str:
    sub = await get_or_create_subscription(tenant, db)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account")
    await db.commit()
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=settings.STRIPE_SUCCESS_URL,
    )
    return session.url


async def _sync_subscription_plan(tenant: Tenant, sub_obj: dict, db: AsyncSession) -> str | None:
    items = sub_obj.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = _plan_from_price_id(price_id)
    if plan:
        _apply_plan(tenant, plan)
    return plan


async def handle_webhook_event(payload: bytes, sig_header: str, db: AsyncSession) -> None:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)

    async with get_admin_db_context() as admin_db:
        existing = await admin_db.get(StripeWebhookEvent, event["id"])
        if existing:
            return

        admin_db.add(StripeWebhookEvent(event_id=event["id"], event_type=event["type"]))

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            tenant_id = session.get("metadata", {}).get("tenant_id")
            if tenant_id:
                tenant = await admin_db.get(Tenant, tenant_id)
                if tenant:
                    line_items = stripe.checkout.Session.list_line_items(session["id"], limit=1)
                    price_id = None
                    if line_items.data:
                        price_id = line_items.data[0].price.id
                    plan = _plan_from_price_id(price_id) or session.get("metadata", {}).get("plan", "starter")
                    _apply_plan(tenant, plan)
                    await set_tenant_rls(admin_db, str(tenant.id))
                    sub = await get_or_create_subscription(tenant, admin_db)
                    sub.stripe_subscription_id = session.get("subscription")
                    sub.status = "active"
                    await log_audit(admin_db, "plan_changed", tenant_id=str(tenant.id), details={"plan": plan, "source": "stripe_checkout"})

        elif event["type"] == "customer.subscription.updated":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj.get("customer")
            result = await admin_db.execute(
                select(Subscription).where(Subscription.stripe_customer_id == customer_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = sub_obj.get("status", "inactive")
                sub.stripe_subscription_id = sub_obj.get("id")
                period_end = sub_obj.get("current_period_end")
                if period_end:
                    sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
                tenant = await admin_db.get(Tenant, sub.tenant_id)
                if tenant and sub_obj.get("status") in ("active", "trialing"):
                    await set_tenant_rls(admin_db, str(tenant.id))
                    plan = await _sync_subscription_plan(tenant, sub_obj, admin_db)
                    if plan:
                        await log_audit(
                            admin_db,
                            "plan_changed",
                            tenant_id=str(tenant.id),
                            details={"plan": plan, "source": "stripe_subscription_updated"},
                        )

        elif event["type"] == "customer.subscription.deleted":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj.get("customer")
            result = await admin_db.execute(
                select(Subscription).where(Subscription.stripe_customer_id == customer_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "canceled"
                tenant = await admin_db.get(Tenant, sub.tenant_id)
                if tenant:
                    _apply_plan(tenant, "free")
                    await set_tenant_rls(admin_db, str(tenant.id))
                    await log_audit(
                        admin_db,
                        "plan_changed",
                        tenant_id=str(tenant.id),
                        details={"plan": "free", "source": "stripe_subscription_deleted"},
                    )

        elif event["type"] == "invoice.payment_failed":
            sub_obj = event["data"]["object"]
            customer_id = sub_obj.get("customer")
            result = await admin_db.execute(
                select(Subscription).where(Subscription.stripe_customer_id == customer_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                await set_tenant_rls(admin_db, str(sub.tenant_id))
                sub.status = "past_due"

        await admin_db.commit()
