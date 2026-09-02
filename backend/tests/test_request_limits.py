import asyncio
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.core.request_limits import MultipartSpoolLimitMiddleware


def _scope(content_length: bytes | None = None) -> Scope:
    headers = [(b"content-type", b"multipart/form-data; boundary=example")]
    if content_length is not None:
        headers.append((b"content-length", content_length))
    return cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "raw_path": b"/upload",
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "server": ("test", 80),
            "client": ("127.0.0.1", 1),
            "state": {"request_id": "request-limit-test"},
        },
    )


async def _invoke(
    middleware: MultipartSpoolLimitMiddleware,
    scope: Scope,
    messages: list[Message] | None = None,
) -> list[Message]:
    incoming = iter(messages or [{"type": "http.request", "body": b"", "more_body": False}])
    sent: list[Message] = []

    async def receive() -> Message:
        return next(incoming)

    async def send(message: Message) -> None:
        sent.append(message)

    await middleware(scope, receive, send)
    return sent


def _status(messages: list[Message]) -> int:
    return cast(
        int,
        next(item["status"] for item in messages if item["type"] == "http.response.start"),
    )


@pytest.mark.asyncio
async def test_multipart_limit_rejects_declared_and_streamed_oversize_bodies() -> None:
    called = False

    async def consume(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        del scope
        called = True
        while (await receive()).get("more_body", False):
            pass
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = MultipartSpoolLimitMiddleware(consume, request_max_bytes=10, capacity_bytes=20)
    declared = await _invoke(middleware, _scope(b"11"))
    assert _status(declared) == 413
    assert called is False

    streamed = await _invoke(
        middleware,
        _scope(),
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        ],
    )
    assert _status(streamed) == 413


@pytest.mark.asyncio
async def test_multipart_spool_budget_rejects_concurrent_capacity_and_recovers() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        entered.set()
        await release.wait()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = MultipartSpoolLimitMiddleware(hold, request_max_bytes=80, capacity_bytes=100)
    first = asyncio.create_task(_invoke(middleware, _scope(b"80")))
    await entered.wait()

    rejected = await _invoke(middleware, _scope(b"30"))
    assert _status(rejected) == 503
    release.set()
    assert _status(await first) == 204

    entered.clear()
    recovered = asyncio.create_task(_invoke(middleware, _scope(b"30")))
    await entered.wait()
    assert _status(await recovered) == 204
