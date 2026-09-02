import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass


async def _bounded_cleanup(
    name: str,
    callback: Callable[[], Awaitable[None]],
    *,
    timeout_seconds: float,
) -> None:
    logger = logging.getLogger("mcplica.lifecycle")

    async def invoke() -> None:
        await callback()

    task: asyncio.Task[None] = asyncio.create_task(invoke(), name=f"close-{name}")
    try:
        async with asyncio.timeout(timeout_seconds):
            await asyncio.shield(task)
    except TimeoutError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        logger.warning(
            "resource_close_timed_out",
            extra={"component": name, "error_code": "shutdown_timeout"},
        )
    except BaseException as exc:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        logger.warning(
            "resource_close_failed",
            extra={"component": name, "error_code": type(exc).__name__},
        )


def register_bounded_close(
    stack: AsyncExitStack,
    *,
    name: str,
    callback: Callable[[], Awaitable[None]],
    timeout_seconds: float,
) -> None:
    stack.push_async_callback(
        _bounded_cleanup,
        name,
        callback,
        timeout_seconds=timeout_seconds,
    )


@dataclass(frozen=True, slots=True)
class ManagedDispatcher:
    name: str
    task: asyncio.Task[None]
    stop_event: asyncio.Event
    wake: Callable[[], None]


class DispatcherGroup:
    def __init__(self, *, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._dispatchers: list[ManagedDispatcher] = []

    def add(
        self,
        *,
        name: str,
        task: asyncio.Task[None],
        stop_event: asyncio.Event,
        wake: Callable[[], None],
    ) -> None:
        self._dispatchers.append(ManagedDispatcher(name, task, stop_event, wake))

    async def shutdown(self) -> None:
        if not self._dispatchers:
            return
        logger = logging.getLogger("mcplica.lifecycle")
        for dispatcher in self._dispatchers:
            dispatcher.stop_event.set()
            try:
                dispatcher.wake()
            except Exception as exc:
                logger.warning(
                    "dispatcher_wake_failed",
                    extra={
                        "component": dispatcher.name,
                        "error_code": type(exc).__name__,
                    },
                )
        tasks = [dispatcher.task for dispatcher in self._dispatchers]
        try:
            async with asyncio.timeout(self._timeout_seconds):
                results = await asyncio.gather(*tasks, return_exceptions=True)
        except TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.warning(
                "dispatcher_shutdown_timed_out",
                extra={"component": "dispatchers", "error_code": "shutdown_timeout"},
            )
        for dispatcher, result in zip(self._dispatchers, results, strict=True):
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                logger.warning(
                    "dispatcher_shutdown_failed",
                    extra={
                        "component": dispatcher.name,
                        "error_code": type(result).__name__,
                    },
                )
