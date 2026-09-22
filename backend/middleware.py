"""Request logging and the global error envelope.

`01_architecture.md` § 10 requires every request to log
``method, path, status_code, latency_ms, user_id (if auth), request_id`` as JSON.

`03_backend_spec.md` § 4 requires *every* error response to be
``{"error": {"code", "message", "details"}}``. Registering handlers here rather than
raising `HTTPException` per endpoint means a route cannot accidentally emit FastAPI's
default ``{"detail": ...}`` shape, which would be a contract mismatch.
"""

import json
import logging
import sys
import time
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# § 4 status -> code. OCR failure is 422 `ocr_failed`, but a Pydantic body failure is
# also 422 `validation_error`, so 422 has no single default and is always explicit.
STATUS_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    504: "upstream_timeout",
}


class AppError(Exception):
    """Raised by routers and services; rendered into the § 4 envelope."""

    def __init__(self, status_code: int, code: str, message: str,
                 details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(status_code: int, code: str, message: str,
                   details: Optional[dict[str, Any]] = None,
                   request_id: Optional[str] = None) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "details": details or {}}}
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", None)
        if payload is None:
            payload = {"message": record.getMessage()}
        return json.dumps({"level": record.levelname.lower(), **payload},
                          ensure_ascii=False)


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("minijurinex")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()


def log_event(**payload: Any) -> None:
    """Structured log line. Used for request, Gemini and OCR events alike."""
    logger.info("", extra={"payload": payload})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        request.state.user_id = None

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The handler below turns this into a 500 envelope; log it as one here so
            # the latency line is not lost when a request blows up.
            log_event(
                event="request",
                method=request.method,
                path=request.url.path,
                status_code=500,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                user_id=getattr(request.state, "user_id", None),
                request_id=request_id,
            )
            raise

        log_event(
            event="request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            user_id=getattr(request.state, "user_id", None),
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details,
                              getattr(request.state, "request_id", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request,
                                exc: RequestValidationError) -> JSONResponse:
        return error_response(
            422,
            "validation_error",
            "Request validation failed.",
            {"errors": json.loads(json.dumps(exc.errors(), default=str))},
            getattr(request.state, "request_id", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request,
                          exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, "internal_error")
        message = exc.detail if isinstance(exc.detail, str) else code
        return error_response(exc.status_code, code, message, {},
                              getattr(request.state, "request_id", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log_event(event="unhandled_exception", error=repr(exc), request_id=request_id)
        # Deliberately opaque: internal detail does not belong in a client response.
        return error_response(500, "internal_error", "An unexpected error occurred.",
                              {}, request_id)
