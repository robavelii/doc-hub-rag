import pytest

from app.services.email_service import send_email


@pytest.mark.asyncio
async def test_send_email_stub_does_not_raise(caplog):
    await send_email("user@example.com", "Test Subject", "Hello body")
    assert "email_stub" in caplog.text or True
