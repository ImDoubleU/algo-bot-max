"""Request correlation for access diagnostics; never record launch credentials."""

import logging
import time
from contextvars import ContextVar
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware

_request_id: ContextVar[str] = ContextVar("binding_request_id", default="background")
logger = logging.getLogger(__name__)


def binding_request_id() -> str:
    return _request_id.get()


class BindingDiagnosticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not (request.url.path.startswith("/api/v1/access/")
                or request.url.path == "/api/v1/miniapp/session"):
            return await call_next(request)
        try:
            request_id = str(UUID(request.headers.get("X-Request-ID", "")))
        except (ValueError, AttributeError):
            request_id = str(uuid4())
        context = _request_id.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "binding_request request_id=%s method=%s path=%r "
                "outcome=%s status=%s elapsed_ms=%s",
                request_id, request.method, request.url.path,
                "failed" if response.status_code >= 500 else (
                    "ok" if response.status_code < 400 else "denied"
                ),
                response.status_code, round((time.monotonic() - started) * 1000),
            )
            return response
        except Exception as exc:
            # Exception text may contain SQL parameters, URLs or user input.
            logger.error(
                "binding_request request_id=%s method=%s path=%r "
                "outcome=failed error_type=%s elapsed_ms=%s",
                request_id, request.method, request.url.path, type(exc).__name__,
                round((time.monotonic() - started) * 1000),
            )
            raise
        finally:
            _request_id.reset(context)
