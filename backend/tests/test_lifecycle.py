import asyncio
from contextlib import AsyncExitStack

import pytest

import app.main as main_module
from app.core.config import Settings
from app.core.lifecycle import DispatcherGroup, register_bounded_close


@pytest.mark.parametrize("failure_index", range(7))
async def test_partial_api_client_acquisition_closes_every_prior_client(
    monkeypatch: pytest.MonkeyPatch,
    failure_index: int,
) -> None:
    client_names = [
        "DatabaseClient",
        "RedisClient",
        "DeploymentQueueClient",
        "BuildQueueClient",
        "HttpClient",
        "MilvusVectorClient",
        "FilesystemStorageClient",
    ]
    created: list[str] = []
    closed: list[str] = []

    class _Client:
        def __init__(self, name: str) -> None:
            self.name = name

        async def close(self) -> None:
            closed.append(self.name)

    for index, name in enumerate(client_names):

        def factory(*_args: object, _index: int = index, _name: str = name, **_kwargs: object):
            if _index == failure_index:
                raise RuntimeError(f"injected {_name} acquisition failure")
            created.append(_name)
            return _Client(_name)

        monkeypatch.setattr(main_module, name, factory)

    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        env="test",
        shutdown_timeout_seconds=0.1,
    )
    with pytest.raises(RuntimeError, match="injected"):
        await main_module._create_app_clients(settings)

    assert set(closed) == set(created)
    assert len(closed) == failure_index


async def test_bounded_cleanup_attempts_later_resources_after_timeout_and_error() -> None:
    calls: list[str] = []

    async def healthy() -> None:
        calls.append("healthy")

    async def failing() -> None:
        calls.append("failing")
        raise RuntimeError("close failed")

    async def stuck() -> None:
        calls.append("stuck")
        await asyncio.Future()

    stack = AsyncExitStack()
    await stack.__aenter__()
    register_bounded_close(stack, name="healthy", callback=healthy, timeout_seconds=0.02)
    register_bounded_close(stack, name="failing", callback=failing, timeout_seconds=0.02)
    register_bounded_close(stack, name="stuck", callback=stuck, timeout_seconds=0.02)

    await asyncio.wait_for(stack.aclose(), timeout=0.25)

    assert calls == ["stuck", "failing", "healthy"]


async def test_dispatcher_shutdown_signals_all_and_cancels_overdue_task() -> None:
    stops = [asyncio.Event(), asyncio.Event()]
    wakes: list[int] = []

    async def stopped(index: int) -> None:
        await stops[index].wait()

    async def stuck() -> None:
        await asyncio.Future()

    normal_task = asyncio.create_task(stopped(0))
    stuck_task = asyncio.create_task(stuck())
    group = DispatcherGroup(timeout_seconds=0.02)
    group.add(
        name="normal",
        task=normal_task,
        stop_event=stops[0],
        wake=lambda: wakes.append(0),
    )
    group.add(
        name="stuck",
        task=stuck_task,
        stop_event=stops[1],
        wake=lambda: wakes.append(1),
    )

    await asyncio.wait_for(group.shutdown(), timeout=0.25)

    assert all(stop.is_set() for stop in stops)
    assert wakes == [0, 1]
    assert normal_task.done()
    assert stuck_task.cancelled()
