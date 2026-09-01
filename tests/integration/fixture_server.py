"""Owned, restartable HTTP fixture used only by the Compose acceptance harness."""

from __future__ import annotations

import asyncio
import socket
import time
from contextlib import suppress
from dataclasses import dataclass

import httpx
import uvicorn
from starlette.applications import Starlette


@dataclass(slots=True)
class FixtureServer:
    app: Starlette
    port: int
    startup_timeout: float = 20
    shutdown_timeout: float = 15
    server: uvicorn.Server | None = None
    task: asyncio.Task[None] | None = None
    listener: socket.socket | None = None

    async def start(self) -> None:
        if self.listener is not None or self.task is not None:
            raise RuntimeError("fixture server is already started")
        try:
            # create_server enables SO_REUSEADDR on POSIX, allowing a stopped
            # fixture to rebind despite its accepted connections' TIME_WAIT.
            # It does not enable SO_REUSEPORT or share an active listener.
            self.listener = socket.create_server(("0.0.0.0", self.port))
        except OSError as exc:
            raise RuntimeError(f"fixture port {self.port} is unavailable") from exc
        self.port = self.listener.getsockname()[1]
        self.listener.setblocking(False)
        try:
            self.server = uvicorn.Server(
                uvicorn.Config(
                    self.app,
                    host="0.0.0.0",
                    port=self.port,
                    log_level="warning",
                    access_log=False,
                    ws="none",
                    timeout_graceful_shutdown=max(1, int(self.shutdown_timeout / 2)),
                )
            )
            self.task = asyncio.create_task(self.server.serve(sockets=[self.listener]))
            deadline = time.monotonic() + self.startup_timeout
            async with httpx.AsyncClient(trust_env=False, timeout=0.5) as client:
                while time.monotonic() < deadline:
                    if self.task.done():
                        await self.task
                        raise RuntimeError(f"fixture on port {self.port} stopped during startup")
                    try:
                        response = await client.get(f"http://127.0.0.1:{self.port}/healthz")
                        if response.status_code == 200:
                            return
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.05)
            raise RuntimeError(f"fixture on port {self.port} did not become healthy")
        except BaseException:
            # Preserve the startup/cancellation error while still releasing the
            # owned socket and task. Never stop an unrelated port's process.
            with suppress(Exception):
                await self.stop()
            raise

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        try:
            if self.task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(self.task), self.shutdown_timeout)
                except (TimeoutError, asyncio.CancelledError):
                    if self.server is not None:
                        self.server.force_exit = True
                    self.task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self.task
                    raise
        finally:
            if self.listener is not None:
                self.listener.close()
            self.server = None
            self.task = None
            self.listener = None
