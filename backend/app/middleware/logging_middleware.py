import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("rag.api")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        tenant = getattr(request.state, "tenant", None)
        user = getattr(request.state, "user", None)
        log_entry = {
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
            "tenant_id": str(tenant.id) if tenant else None,
            "user_id": str(user.id) if user else None,
        }
        logger.info(json.dumps(log_entry))
        return response
