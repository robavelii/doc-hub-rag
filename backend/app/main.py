import json
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    admin,
    api_keys,
    auth,
    billing,
    conversations,
    documents,
    feedback,
    integrations,
    query,
    usage,
    widget,
)
from app.services.provider_health import get_provider_health
from app.services.storage_service import get_s3_client
from app.utils.production_guard import validate_production_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings(settings)
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(dsn=settings.SENTRY_DSN, integrations=[FastApiIntegration()], environment=settings.APP_ENV)
        except ImportError:
            logger.warning("sentry-sdk not installed; skipping Sentry init")
    yield


app = FastAPI(title="Doc-Hub API", version="1.0.0", lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except ImportError:
    pass

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(usage.router)
app.include_router(widget.router)
app.include_router(integrations.router)
app.include_router(admin.router)
app.include_router(conversations.router)
app.include_router(feedback.router)
app.include_router(api_keys.router)
app.include_router(billing.router)


async def _check_postgres() -> dict:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:200]}


async def _check_redis() -> dict:
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.aclose()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:200]}


def _check_minio() -> dict:
    try:
        get_s3_client().head_bucket(Bucket=settings.S3_BUCKET)
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)[:200]}


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    postgres = await _check_postgres()
    redis_check = await _check_redis()
    minio = _check_minio()
    providers = await get_provider_health()
    checks = {
        "postgres": postgres,
        "redis": redis_check,
        "minio": minio,
        "providers": providers,
    }
    all_ok = (
        postgres["status"] == "ok"
        and redis_check["status"] == "ok"
        and minio["status"] == "ok"
    )
    return Response(
        content=json.dumps({"status": "ok" if all_ok else "degraded", "checks": checks}),
        media_type="application/json",
        status_code=200 if all_ok else 503,
    )


@app.get("/health")
async def health():
    postgres = await _check_postgres()
    redis_check = await _check_redis()
    minio = _check_minio()
    providers = await get_provider_health()
    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "ai_provider": settings.AI_PROVIDER,
        "providers": providers,
        "checks": {
            "api": "ok",
            "postgres": postgres,
            "redis": redis_check,
            "minio": minio,
            "providers": providers,
        },
    }
