import asyncio

import httpx
import pytest
from mcp_contracts import ServerDefinition
from pydantic import AnyHttpUrl

from app.clients.api_client import ApiClient
from app.executor.errors import (
    UpstreamConnectionError,
    UpstreamRequestTooLargeError,
    UpstreamResponseTooLargeError,
    UpstreamTimeoutError,
)
from app.executor.request_builder import BuiltRequest, QueryParameter
from app.security.url_policy import UpstreamUrlPolicy


def _request(body: object | None = None) -> BuiltRequest:
    return BuiltRequest(
        method="POST",
        url="https://8.8.8.8/items",
        headers=(("Accept", "application/json"),),
        query=(QueryParameter("tag", "a/b"),),
        json_body=body,
    )


@pytest.mark.asyncio
async def test_api_client_pools_and_maps_without_leaking_upstream_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b"tag=a%2Fb"
        return httpx.Response(403, json={"secret": "must-not-leak"})

    policy = UpstreamUrlPolicy([ServerDefinition(id="main", url=AnyHttpUrl("https://8.8.8.8"))])
    client = ApiClient(policy, transport=httpx.MockTransport(handler))
    try:
        result = await client.execute(
            _request({"name": "value"}),
            timeout_ms=1_000,
            max_request_bytes=10_000,
            max_response_bytes=10_000,
        )
    finally:
        await client.close()

    assert result.status_code == 403
    assert result.data == {"error": "upstream_http_error", "status": 403}


@pytest.mark.asyncio
async def test_api_client_enforces_request_and_streamed_response_bounds() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2_000, headers={"content-type": "text/plain"})

    policy = UpstreamUrlPolicy([ServerDefinition(id="main", url=AnyHttpUrl("https://8.8.8.8"))])
    client = ApiClient(policy, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(UpstreamRequestTooLargeError):
            await client.execute(
                _request({"value": "x" * 2_000}),
                timeout_ms=1_000,
                max_request_bytes=1_024,
                max_response_bytes=10_000,
            )
        with pytest.raises(UpstreamResponseTooLargeError):
            await client.execute(
                _request({}),
                timeout_ms=1_000,
                max_request_bytes=10_000,
                max_response_bytes=1_024,
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_client_does_not_follow_redirects_or_trust_malformed_lengths() -> None:
    response_number = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal response_number
        response_number += 1
        if response_number == 1:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/latest"})
        return httpx.Response(
            200,
            content=b"value",
            headers={"content-type": "text/plain", "content-length": "not-a-number"},
        )

    policy = UpstreamUrlPolicy([ServerDefinition(id="main", url=AnyHttpUrl("https://8.8.8.8"))])
    client = ApiClient(policy, transport=httpx.MockTransport(handler))
    try:
        redirected = await client.execute(
            _request({}),
            timeout_ms=1_000,
            max_request_bytes=10_000,
            max_response_bytes=10_000,
        )
        with pytest.raises(UpstreamConnectionError):
            await client.execute(
                _request({}),
                timeout_ms=1_000,
                max_request_bytes=10_000,
                max_response_bytes=10_000,
            )
    finally:
        await client.close()
    assert redirected.is_error is True
    assert redirected.data == {"error": "upstream_http_error", "status": 302}


@pytest.mark.asyncio
async def test_api_client_enforces_whole_operation_deadline() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"ok": True})

    policy = UpstreamUrlPolicy(
        [ServerDefinition.model_validate({"id": "main", "url": "https://8.8.8.8"})]
    )
    client = ApiClient(policy, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(UpstreamTimeoutError):
            await client.execute(
                BuiltRequest("GET", "https://8.8.8.8/value", (), ()),
                timeout_ms=10,
                max_request_bytes=1_024,
                max_response_bytes=1_024,
            )
    finally:
        await client.close()
