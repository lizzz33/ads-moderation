import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from observability.metrics import HTTP_ERRORS_TOTAL


class ErrorMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clean_path = re.sub(r"[^a-zA-Z0-9_/]", "_", request.url.path)
        clean_path = clean_path.replace("/", "_").strip("_")

        try:
            response = await call_next(request)

            handler = getattr(request.state, "handler", "unknown")

            if 400 <= response.status_code < 600:
                HTTP_ERRORS_TOTAL.labels(
                    status_code=str(response.status_code), method=request.method, handler=handler
                ).inc()

            return response
        except Exception:
            HTTP_ERRORS_TOTAL.labels(
                status_code="500", method=request.method, handler="internal_error"
            ).inc()
            raise
