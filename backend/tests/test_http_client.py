import httpx
import pytest

from app.clients.http import HttpClient
from app.core.exceptions import (
    ClientUnavailableError,
    PayloadTooLargeError,
    SecurityPolicyError,
)
from app.core.network_policy import UrlPolicy


async def _public_resolver(_hostname: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.asyncio
async def test_bounded_fetch_revalidates_redirect_and_enforces_size() -> None:
    requests: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            (
                str(request.url),
                request.headers["Host"],
                request.extensions.get("sni_hostname"),
            )
        )
        if request.headers["Host"] == "public.example":
            return httpx.Response(302, headers={"Location": "https://other.example/spec"})
        return httpx.Response(200, content=b"{}")

    client = HttpClient(transport=httpx.MockTransport(handler))
    policy = UrlPolicy(resolver=_public_resolver)
    try:
        response = await client.fetch_bounded(
            "https://public.example/start",
            policy=policy,
            max_bytes=10,
            max_redirects=3,
        )
        assert response.body == b"{}"
        assert requests == [
            ("https://93.184.216.34/start", "public.example", "public.example"),
            ("https://93.184.216.34/spec", "other.example", "other.example"),
        ]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bounded_fetch_rejects_oversize_and_private_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/private":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/latest"})
        return httpx.Response(200, content=b"too many bytes")

    client = HttpClient(transport=httpx.MockTransport(handler))
    policy = UrlPolicy(resolver=_public_resolver)
    try:
        with pytest.raises(PayloadTooLargeError):
            await client.fetch_bounded(
                "https://public.example/large",
                policy=policy,
                max_bytes=4,
                max_redirects=1,
            )
        with pytest.raises(SecurityPolicyError):
            await client.fetch_bounded(
                "https://public.example/private",
                policy=policy,
                max_bytes=100,
                max_redirects=1,
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bounded_fetch_retries_transient_5xx_with_bounded_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, content=b"{}")

    async def record_delay(value: float) -> None:
        delays.append(value)

    client = HttpClient(
        transport=httpx.MockTransport(handler),
        sleep=record_delay,
        jitter=lambda: 0.0,
    )
    try:
        response = await client.fetch_bounded(
            "https://public.example/spec",
            policy=UrlPolicy(resolver=_public_resolver),
            max_bytes=10,
            max_redirects=0,
            max_attempts=2,
        )
        assert response.body == b"{}"
        assert attempts == 2
        assert delays == [0.25]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bounded_fetch_stops_after_configured_attempts() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    async def no_wait(_value: float) -> None:
        return None

    client = HttpClient(
        transport=httpx.MockTransport(handler),
        sleep=no_wait,
        jitter=lambda: 0.0,
    )
    try:
        with pytest.raises(ClientUnavailableError):
            await client.fetch_bounded(
                "https://public.example/spec",
                policy=UrlPolicy(resolver=_public_resolver),
                max_bytes=10,
                max_redirects=0,
                max_attempts=2,
            )
        assert attempts == 2
    finally:
        await client.close()
