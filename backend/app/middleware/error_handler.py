import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("rag.api")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if isinstance(exc.detail, str) else exc.detail,
                "code": exc.status_code,
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "code": 422,
                "details": exc.errors(),
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.error(json.dumps({"request_id": request_id, "error": str(exc), "type": type(exc).__name__}))
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": 500,
                "request_id": request_id,
            },
        )
