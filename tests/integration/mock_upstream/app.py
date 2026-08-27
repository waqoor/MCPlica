from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

_MAX_FIXTURE_BODY_BYTES = 2_000_000


async def echo(request: Request) -> JSONResponse:
    body = await request.body()
    if len(body) > _MAX_FIXTURE_BODY_BYTES:
        return JSONResponse({"error": "fixture_body_too_large"}, status_code=413)
    status_code = (
        201 if request.method == "POST" and request.url.path.rstrip("/") == "/api/widgets" else 200
    )
    return JSONResponse(
        {
            "method": request.method,
            "path": request.url.path,
            "query": list(request.query_params.multi_items()),
            "content_type": request.headers.get("content-type"),
            "authorization": request.headers.get("authorization"),
            "api_key": request.headers.get("x-api-key"),
            "body_bytes": len(body),
        },
        status_code=status_code,
    )


routes = [
    Route(
        "/{path:path}",
        echo,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
]

app = Starlette(routes=routes)
