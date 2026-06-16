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
