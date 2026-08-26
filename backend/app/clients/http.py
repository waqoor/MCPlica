import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.clients.base import AsyncClient
from app.core.exceptions import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientError,
    ClientRateLimitError,
    ClientResponseError,
    ClientTimeoutError,
    ClientUnavailableError,
    PayloadTooLargeError,
    SecurityPolicyError,
)
from app.core.network_policy import UrlPolicy

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_SENSITIVE_FETCH_HEADERS = frozenset(
    {"authorization", "connection", "cookie", "host", "proxy-authorization"}
)


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    status_code: int
    url: str
    headers: dict[str, str]
    body: bytes


def _pinned_destination(url: str, address: str) -> tuple[str, str]:
    """Return an address-pinned URL and its original HTTP Host authority."""

    parsed = urlsplit(url)
    address_authority = f"[{address}]" if ":" in address else address
    if parsed.port is not None:
        address_authority = f"{address_authority}:{parsed.port}"
    return (
        urlunsplit((parsed.scheme, address_authority, parsed.path, parsed.query, "")),
        parsed.netloc,
    )


class HttpClient(AsyncClient):
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        timeout = httpx.Timeout(
            connect=timeout_seconds,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=timeout_seconds,
        )
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
            transport=transport,
        )
        self._sleep = sleep
        self._jitter = jitter

    async def health(self) -> bool:
        return not self.client.is_closed

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self.client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ClientTimeoutError("HTTP request timed out") from exc
        except httpx.TransportError as exc:
            raise ClientConnectionError("HTTP request failed to connect") from exc
        return response

    async def fetch_bounded(
        self,
        url: str,
        *,
        policy: UrlPolicy,
        max_bytes: int,
        max_redirects: int,
        headers: dict[str, str] | None = None,
        max_attempts: int = 3,
    ) -> FetchedResponse:
        if max_bytes <= 0:
            raise ValueError("Remote source byte limit must be positive")
        if max_redirects < 0:
            raise ValueError("Remote source redirect limit cannot be negative")
        if not 1 <= max_attempts <= 8:
            raise ValueError("Remote source attempts must be between 1 and 8")
        current_url = url
        safe_headers = {
            name: value
            for name, value in (headers or {}).items()
            if name.casefold() not in _SENSITIVE_FETCH_HEADERS
        }
        redirect_count = 0
        while True:
            redirect_url: str | None = None
            for attempt in range(1, max_attempts + 1):
                validated = await policy.validate(current_url)
                pinned_url, host = _pinned_destination(
                    validated.url,
                    validated.resolved_addresses[0],
                )
                request = self.client.build_request(
                    "GET",
                    pinned_url,
                    headers={**safe_headers, "Host": host, "Connection": "close"},
                    extensions={"sni_hostname": validated.hostname},
                )
                response: httpx.Response | None = None
                retry_error: ClientConnectionError | ClientTimeoutError | ClientError = (
                    ClientUnavailableError("Remote source fetch failed")
                )
                try:
                    response = await self.client.send(request, stream=True)
                    if response.status_code in REDIRECT_STATUSES:
                        if redirect_count >= max_redirects:
                            raise SecurityPolicyError("Remote source exceeded redirect limit")
                        location = response.headers.get("Location")
                        if not location:
                            raise ClientResponseError("Remote source redirect omitted Location")
                        redirect_url = urljoin(validated.url, location)
                    elif response.status_code in {401, 403}:
                        raise ClientAuthenticationError("Remote source rejected authentication")
                    elif response.status_code == 429:
                        retry_error = ClientRateLimitError(
                            "Remote source rate limit persisted after retries"
                        )
                    elif response.status_code >= 500:
                        retry_error = ClientUnavailableError(
                            "Remote source remained unavailable after retries",
                            details={"status_code": response.status_code},
                        )
                    elif response.status_code == 304:
                        return FetchedResponse(
                            status_code=304,
                            url=validated.url,
                            headers=dict(response.headers),
                            body=b"",
                        )
                    elif response.status_code >= 400:
                        raise ClientResponseError(
                            f"Remote source returned HTTP {response.status_code}",
                            details={"status_code": response.status_code},
                        )
                    else:
                        declared_length = response.headers.get("Content-Length")
                        if declared_length is not None:
                            try:
                                declared_size = int(declared_length)
                            except ValueError:
                                declared_size = 0
                            if declared_size > max_bytes:
                                raise PayloadTooLargeError(
                                    "Remote source exceeds configured byte limit"
                                )
                        chunks: list[bytes] = []
                        total = 0
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > max_bytes:
                                raise PayloadTooLargeError(
                                    "Remote source exceeds configured byte limit"
                                )
                            chunks.append(chunk)
                        return FetchedResponse(
                            status_code=response.status_code,
                            url=validated.url,
                            headers=dict(response.headers),
                            body=b"".join(chunks),
                        )
                except httpx.TimeoutException as exc:
                    retry_error = ClientTimeoutError("Remote source fetch timed out")
                    retry_error.__cause__ = exc
                except httpx.TransportError as exc:
                    retry_error = ClientConnectionError("Remote source fetch failed to connect")
                    retry_error.__cause__ = exc
                finally:
                    if response is not None:
                        await response.aclose()
                if redirect_url is not None:
                    break
                if attempt == max_attempts:
                    raise retry_error
                await self._backoff(attempt)
            if redirect_url is None:
                raise SecurityPolicyError("Remote source redirect validation failed")
            current_url = redirect_url
            redirect_count += 1

    async def _backoff(self, attempt: int) -> None:
        base = min(8.0, 0.25 * (2 ** (attempt - 1)))
        await self._sleep(base + base * 0.2 * self._jitter())

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
