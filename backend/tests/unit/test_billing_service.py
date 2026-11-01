import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.tenant import Tenant
from app.services.billing_service import (
    _apply_plan,
    _plan_from_price_id,
    create_portal_session,
    get_or_create_subscription,
)


def test_apply_plan_updates_limits():
    tenant = Tenant(name="T", slug="t", plan="free")
    _apply_plan(tenant, "pro")
    assert tenant.plan == "pro"
    assert tenant.monthly_token_limit == 10_000_000


def test_plan_from_price_id_unknown():
    assert _plan_from_price_id("price_unknown") is None


@pytest.mark.asyncio
async def test_get_or_create_subscription_returns_existing():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    db = AsyncMock()
    existing = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result)

    sub = await get_or_create_subscription(tenant, db)
    assert sub is existing


@pytest.mark.asyncio
async def test_create_portal_session_commits():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    sub = MagicMock()
    sub.stripe_customer_id = "cus_123"

    db = AsyncMock()
    with patch("app.services.billing_service.get_or_create_subscription", return_value=sub):
        with patch("app.services.billing_service.stripe") as mock_stripe:
            mock_stripe.billing_portal.Session.create.return_value = MagicMock(url="https://portal")
            url = await create_portal_session(tenant, db)
            assert url == "https://portal"
            db.commit.assert_awaited()


def test_parse_webhook_event_returns_plain_dicts(monkeypatch):
    import json
    import time

    import stripe

    from app.services import billing_service

    secret = "whsec_test_secret"
    monkeypatch.setattr(billing_service.settings, "STRIPE_WEBHOOK_SECRET", secret)
    payload = json.dumps(
        {
            "id": "evt_1",
            "object": "event",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_1", "customer": "cus_1", "metadata": {"tenant_id": "t"}}},
        }
    )
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload}", secret)
    event = billing_service.parse_webhook_event(payload.encode(), f"t={ts},v1={sig}")
    obj = event["data"]["object"]
    assert isinstance(obj, dict)
    assert obj.get("metadata", {}).get("tenant_id") == "t"


def test_period_end_reads_item_level_field():
    from app.services.billing_service import _period_end

    assert _period_end({"current_period_end": 10}) == 10
    assert _period_end({"items": {"data": [{"current_period_end": 20}]}}) == 20
    assert _period_end({}) is None


def test_validation_errors_from_model_validators_return_422_not_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import BaseModel, model_validator

    from app.middleware.error_handler import register_exception_handlers

    class Body(BaseModel):
        a: int | None = None

        @model_validator(mode="after")
        def check(self):
            raise ValueError("bad body")

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/x")
    def endpoint(body: Body):
        return {}

    r = TestClient(app, raise_server_exceptions=False).post("/x", json={})
    assert r.status_code == 422
    assert "bad body" in str(r.json()["details"])
