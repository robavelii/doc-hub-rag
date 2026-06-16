import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.usage_service import (
    PLAN_LIMITS,
    check_storage_limit,
    get_storage_usage,
    record_query_usage,
    record_storage_usage,
)


@pytest.mark.asyncio
async def test_record_storage_usage_commits_event():
    db = AsyncMock()
    tenant_id = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())

    await record_storage_usage(tenant_id, 512, ref_id, db)

    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_record_query_usage_commits_event():
    db = AsyncMock()
    tenant_id = str(uuid.uuid4())

    await record_query_usage(tenant_id, 42, str(uuid.uuid4()), db)

    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_check_storage_limit_raises_when_exceeded():
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = "free"

    db = AsyncMock()
    with patch("app.services.usage_service.get_storage_usage", return_value=PLAN_LIMITS["free"]["storage"]):
        with pytest.raises(HTTPException) as exc:
            await check_storage_limit(tenant, 1, db)
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_storage_usage_sums_events():
    db = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 1024
    db.execute = AsyncMock(return_value=result)

    total = await get_storage_usage(str(uuid.uuid4()), db)
    assert total == 1024
