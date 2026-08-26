import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

_MISSING = object()


async def bounded_map[Input, Output](
    values: Sequence[Input],
    function: Callable[[Input], Awaitable[Output]],
    *,
    limit: int,
) -> list[Output]:
    """Map async work with O(limit) tasks while preserving input order."""
    if limit < 1:
        raise ValueError("Concurrency limit must be positive")
    if not values:
        return []
    iterator = iter(enumerate(values))
    results: list[Output | object] = [_MISSING] * len(values)

    async def worker() -> None:
        for index, value in iterator:
            results[index] = await function(value)

    tasks = [asyncio.create_task(worker()) for _ in range(min(limit, len(values)))]
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    if any(value is _MISSING for value in results):
        raise RuntimeError("Bounded async map did not complete all values")
    return [cast(Output, value) for value in results]
