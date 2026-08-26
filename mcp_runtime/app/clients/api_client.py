from dataclasses import dataclass
from typing import Any

import httpx

from app.executor.request_builder import BuiltRequest


@dataclass
class UpstreamResult:
    status_code: int
    content_type: str
    data: Any

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400


class ApiClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(follow_redirects=False)

    async def execute(self, request: BuiltRequest, *, timeout_ms: int, max_response_bytes: int) -> UpstreamResult:
        response = await self.client.request(
            request.method,
            request.url,
            params=request.query,
            headers=request.headers,
            json=request.json_body,
            data=request.form_body,
            timeout=timeout_ms / 1000,
        )
        body = response.content
        if len(body) > max_response_bytes:
            raise RuntimeError(
                f"Upstream response exceeded configured limit ({len(body)} > {max_response_bytes})"
            )
        content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
        if content_type == "application/json" or content_type.endswith("+json"):
            try:
                data: Any = response.json()
            except ValueError:
                data = body.decode("utf-8", errors="replace")
        elif content_type.startswith("text/"):
            data = body.decode("utf-8", errors="replace")
        else:
            data = {
                "status": response.status_code,
                "content_type": content_type,
                "bytes": len(body),
                "message": "Binary response body is not forwarded by MCPlica starter runtime",
            }
        return UpstreamResult(response.status_code, content_type, data)

    async def close(self) -> None:
        await self.client.aclose()
