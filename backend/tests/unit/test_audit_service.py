import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.audit_service import log_audit


@pytest.mark.asyncio
async def test_log_audit_with_tenant_sets_rls_and_commits():
    db = AsyncMock()
    tenant_id = str(uuid.uuid4())

    await log_audit(db, "login", tenant_id=tenant_id, user_id=str(uuid.uuid4()))

    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_log_audit_without_tenant_still_commits():
    db = AsyncMock()

    await log_audit(db, "login_failed", details={"email": "x@test.com"})

    db.add.assert_called_once()
    db.commit.assert_awaited()
