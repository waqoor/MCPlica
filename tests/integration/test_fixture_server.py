import asyncio
import socket

import httpx
import pytest
from fixture_server import FixtureServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


def health(_request: Request) -> PlainTextResponse:
    # Server-initiated close ensures the regression exercises TIME_WAIT, not
    # merely an unused listening socket.
    return PlainTextResponse("ok", headers={"Connection": "close"})


@pytest.mark.asyncio
async def test_fixture_restarts_on_same_port_after_live_connections() -> None:
    app = Starlette(routes=[Route("/healthz", health)])
    server = FixtureServer(app, 0)
    for _ in range(3):
        await server.start()
        port = server.port
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.get(f"http://127.0.0.1:{port}/healthz")
                assert response.status_code == 200
        finally:
            await server.stop()
        assert server.listener is None
        assert server.task is None
        await server.stop()
        server = FixtureServer(app, port)


@pytest.mark.asyncio
async def test_fixture_does_not_reuse_another_live_listener() -> None:
    with socket.create_server(("0.0.0.0", 0)) as listener:
        server = FixtureServer(Starlette(), listener.getsockname()[1])
        with pytest.raises(RuntimeError, match="unavailable"):
            await server.start()
        assert server.listener is None
        assert server.task is None
        assert listener.fileno() >= 0


@pytest.mark.asyncio
async def test_unhealthy_startup_releases_port_and_task() -> None:
    server = FixtureServer(Starlette(), 0, startup_timeout=0.15)
    with pytest.raises(RuntimeError, match="did not become healthy"):
        await server.start()
    assert server.task is None
    assert server.listener is None
    replacement = FixtureServer(Starlette(routes=[Route("/healthz", health)]), server.port)
    try:
        await replacement.start()
    finally:
        await replacement.stop()


@pytest.mark.asyncio
async def test_duplicate_start_keeps_original_listener_owned() -> None:
    server = FixtureServer(Starlette(routes=[Route("/healthz", health)]), 0)
    try:
        await server.start()
        original_listener = server.listener
        with pytest.raises(RuntimeError, match="already started"):
            await server.start()
        assert server.listener is original_listener
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_cancelled_startup_releases_resources() -> None:
    server = FixtureServer(Starlette(), 0)
    task = asyncio.create_task(server.start())
    try:
        async with asyncio.timeout(2):
            while server.task is None:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert server.task is None
        assert server.listener is None
    finally:
        task.cancel()
        await server.stop()
