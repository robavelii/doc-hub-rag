"""Refuse startup when production uses known-insecure defaults."""

from app.config import Settings

INSECURE_DEFAULTS: dict[str, tuple[str, ...]] = {
    "JWT_SECRET": (
        "change-this-in-production",
        "change-this-in-production-use-openssl-rand-hex-32",
    ),
    "ENCRYPTION_KEY": ("change-this-32-byte-key-for-fernet",),
    "SUPERADMIN_PASSWORD": ("change-this",),
    "S3_ACCESS_KEY": ("minioadmin",),
    "S3_SECRET_KEY": ("minioadmin",),
}

INSECURE_DATABASE_MARKERS = (
    "postgres:postgres@",
    ":postgres@postgres:",
)


def validate_production_settings(settings: Settings) -> None:
    if settings.APP_ENV.lower() != "production":
        return

    errors: list[str] = []
    for field, bad_values in INSECURE_DEFAULTS.items():
        value = getattr(settings, field, "")
        if value in bad_values:
            errors.append(f"{field} must be changed from default in production")

    for marker in INSECURE_DATABASE_MARKERS:
        if marker in settings.DATABASE_URL or marker in settings.DATABASE_SYNC_URL:
            errors.append("DATABASE_URL must not use default postgres credentials in production")
            break

    if "redis://redis:6379" in settings.REDIS_URL and "@" not in settings.REDIS_URL.split("redis://", 1)[-1]:
        errors.append("REDIS_URL must include authentication in production")

    if errors:
        raise RuntimeError("Production security validation failed: " + "; ".join(errors))
