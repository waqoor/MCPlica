import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from mcp_contracts.json_types import JsonObject, JsonValue
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from app.clients.base import AsyncClient
from app.clients.http import HttpClient
from app.core.exceptions import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientRateLimitError,
    ClientResponseError,
    ClientTimeoutError,
    ClientUnavailableError,
)
from app.observability import observe_openrouter_rate_limit, observe_openrouter_request

ApiKeyResolver = Callable[[], Awaitable[str | None]]
_JSON_OBJECT: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


class OpenRouterClient(AsyncClient):
    def __init__(
        self,
        http: HttpClient,
        api_key_resolver: ApiKeyResolver,
        base_url: str,
        *,
        site_url: str | None = None,
        app_name: str = "MCPlica",
        max_attempts: int = 3,
        timeout_seconds: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http = http
        self._api_key_resolver = api_key_resolver
        self._base_url = base_url.rstrip("/")
        self._site_url = site_url
        self._app_name = app_name
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep

    async def _headers(self) -> dict[str, str]:
        api_key = await self._api_key_resolver()
        if not api_key:
            raise ClientAuthenticationError("OpenRouter is not configured")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": self._app_name,
        }
        if self._site_url:
            headers["HTTP-Referer"] = self._site_url
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> JsonObject:
        operation = {
            "/models": "models",
            "/chat/completions": "chat_completions",
            "/embeddings": "embeddings",
        }.get(path, "unknown")
        started = time.perf_counter()
        outcome = "error"
        try:
            result = await self._request_json_with_retries(
                method,
                path,
                operation=operation,
                payload=payload,
            )
            outcome = "succeeded"
            return result
        except ClientAuthenticationError:
            outcome = "authentication_error"
            raise
        except ClientRateLimitError:
            outcome = "rate_limited"
            raise
        except ClientUnavailableError:
            outcome = "unavailable"
            raise
        except ClientResponseError:
            outcome = "response_error"
            raise
        finally:
            observe_openrouter_request(operation, outcome, time.perf_counter() - started)

    async def _request_json_with_retries(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        payload: dict[str, Any] | None = None,
    ) -> JsonObject:
        headers = await self._headers()
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._http.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            except (ClientConnectionError, ClientTimeoutError) as exc:
                last_error = exc
                if attempt == self._max_attempts:
                    raise ClientUnavailableError("OpenRouter is unavailable") from exc
                await self._backoff(attempt)
                continue
            if response.status_code in {401, 403}:
                raise ClientAuthenticationError("OpenRouter rejected the configured API key")
            if response.status_code == 429:
                observe_openrouter_rate_limit(operation)
                if attempt == self._max_attempts:
                    raise ClientRateLimitError("OpenRouter rate limit persisted after retries")
                await self._backoff(attempt)
                continue
            if response.status_code >= 500:
                if attempt == self._max_attempts:
                    raise ClientUnavailableError(
                        "OpenRouter remained unavailable after retries",
                        details={"status_code": response.status_code},
                    )
                await self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise ClientResponseError(
                    f"OpenRouter returned HTTP {response.status_code}",
                    details={"status_code": response.status_code},
                )
            try:
                data = cast(object, response.json())
                return _JSON_OBJECT.validate_python(data)
            except (ValueError, PydanticValidationError) as exc:
                raise ClientResponseError("OpenRouter returned invalid JSON") from exc
        raise ClientUnavailableError("OpenRouter request failed") from last_error

    async def _backoff(self, attempt: int) -> None:
        base = min(8.0, 0.25 * (2 ** (attempt - 1)))
        await self._sleep(base + random.uniform(0, base * 0.2))

    async def health(self) -> bool:
        try:
            await self.models()
            return True
        except Exception:
            return False

    async def models(self) -> list[JsonObject]:
        payload = await self._request_json("GET", "/models")
        raw_models = payload.get("data", [])
        if not isinstance(raw_models, list):
            raise ClientResponseError("OpenRouter model catalog is malformed")
        return [
            cast(JsonObject, item)
            for item in cast(list[JsonValue], raw_models)
            if isinstance(item, dict)
        ]

    async def chat_completion(self, payload: dict[str, Any]) -> JsonObject:
        return await self._request_json("POST", "/chat/completions", payload=payload)

    async def embeddings(self, payload: dict[str, Any]) -> JsonObject:
        return await self._request_json("POST", "/embeddings", payload=payload)
