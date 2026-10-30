"""Shared HTTP safeguards for the full server and localhost research server."""
import json
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.http")


class HTTPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        origin = request.headers.get("origin")
        # SameSite cookies plus an explicit Origin check protect cookie mutations.
        # Requests without Origin remain available to CLI and service clients.
        same_origin = f"{request.url.scheme}://{request.url.netloc}"
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and origin and origin not in self.allowed_origins and origin != same_origin:
            response = JSONResponse({"detail": "Origin is not permitted"}, status_code=403)
        else:
            try:
                size = int(request.headers.get("content-length", "0"))
                if size < 0 or size > 4_000_000:
                    response = JSONResponse({"detail": "Request body exceeds the 4 MB limit"}, status_code=413)
                else:
                    response = await call_next(request)
            except ValueError:
                response = JSONResponse({"detail": "Invalid request"}, status_code=400)
            except Exception:
                # Do not include request bodies, credentials, URLs with queries or exception strings in the response.
                logger.exception("Unhandled request failure: %s", request_id)
                response = JSONResponse({"detail": "Internal server error", "request_id": request_id}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith(("/app/", "/auth/", "/health")):
            response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(json.dumps({"event": "request", "request_id": request_id,
                               "method": request.method, "route": route.path if route else "unmatched",
                               "status": response.status_code, "duration_ms": round((time.monotonic() - started) * 1000, 2)}))
        return response
