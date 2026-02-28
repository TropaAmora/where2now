"""Request/response logging middleware for FastAPI."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import set_request_id


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        start_time = time.perf_counter()
        response = None
        status = "?"
        try:
            response = await call_next(request)
            status = response.status_code if response is not None else "?"
        except Exception:
            logger.exception("Unhandled exception while processing request")
            status = "error"
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "HTTP %s %s completed in %.2fms with status %s",
                request.method,
                request.url.path,
                duration_ms,
                status,
            )
            set_request_id(None)

        if response is not None:
            response.headers["X-Request-ID"] = request_id
        return response

