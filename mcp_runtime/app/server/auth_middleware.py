import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class StaticBearerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str | None, auth_required: bool) -> None:
        super().__init__(app)
        self.token = token
        self.auth_required = auth_required

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/healthz", "/readyz"}:
            return await call_next(request)
        if not self.auth_required:
            return await call_next(request)
        if not self.token:
            return JSONResponse({"error": "MCP inbound bearer token is not configured"}, status_code=503)
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {self.token}"
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)
