import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest())
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
