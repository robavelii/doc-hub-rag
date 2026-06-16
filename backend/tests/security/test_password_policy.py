import pytest
from fastapi import HTTPException

from app.services.auth_service import validate_password_strength


def test_short_password_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_password_strength("short")
    assert exc.value.status_code == 422


def test_long_password_accepted():
    validate_password_strength("validpassword12")
