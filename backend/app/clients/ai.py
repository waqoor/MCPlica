from typing import Any

import httpx

from app.clients.base import AsyncClient


class OpenRouterClient(AsyncClient):
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        *,
        site_url: str | None = None,
        app_name: str = "MCPlica",
    ) -> None:
        self.api_key = api_key
        headers = {"X-Title": app_name}
        if site_url:
            headers["HTTP-Referer"] = site_url
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=60.0)

    async def health(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = await self.client.get("/models")
            return response.is_success
        except httpx.HTTPError:
            return False

    async def models(self) -> list[dict[str, Any]]:
        response = await self.client.get("/models")
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("data", []))

    async def chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OpenRouter is not configured")
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
