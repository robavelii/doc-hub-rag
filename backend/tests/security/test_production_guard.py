import pytest

from app.config import Settings
from app.utils.production_guard import validate_production_settings


def test_rejects_default_jwt_in_production():
    settings = Settings(APP_ENV="production", JWT_SECRET="change-this-in-production")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_production_settings(settings)


def test_allows_custom_secrets_in_production():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="a" * 64,
        ENCRYPTION_KEY="b" * 32,
        SUPERADMIN_PASSWORD="strong-admin-pass",
        S3_ACCESS_KEY="prodkey",
        S3_SECRET_KEY="prodsecret",
        DATABASE_URL="postgresql+asyncpg://app_user:secret@db:5432/ragdb",
        DATABASE_SYNC_URL="postgresql://app_user:secret@db:5432/ragdb",
        REDIS_URL="redis://:redispass@redis:6379/0",
    )
    validate_production_settings(settings)
