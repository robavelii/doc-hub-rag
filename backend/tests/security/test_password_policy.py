import pytest
from fastapi import HTTPException

from app.services.auth_service import validate_password_strength


def test_short_password_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_password_strength("short")
    assert exc.value.status_code == 422


def test_long_password_accepted():
    validate_password_strength("validpassword12")


def test_password_over_bcrypt_limit_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_password_strength("x" * 73)
    assert exc.value.status_code == 422


def test_verify_password_over_limit_returns_false_not_500():
    from app.services.auth_service import hash_password, verify_password

    hashed = hash_password("validpassword12")
    assert verify_password("validpassword12", hashed)
    assert verify_password("y" * 200, hashed) is False
