from typing import Any

import httpx

from app.clients.base import AsyncClient


class HttpClient(AsyncClient):
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    async def health(self) -> bool:
        return True

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await self.client.request(method, url, **kwargs)

    async def close(self) -> None:
        await self.client.aclose()
