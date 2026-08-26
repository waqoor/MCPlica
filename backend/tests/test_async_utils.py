import asyncio

import pytest

from app.core.async_utils import bounded_map


async def test_bounded_map_preserves_order_and_limits_active_work() -> None:
    active = 0
    peak = 0

    async def double(value: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return value * 2

    assert await bounded_map(list(range(20)), double, limit=3) == [value * 2 for value in range(20)]
    assert peak == 3


async def test_bounded_map_cancels_siblings_on_failure() -> None:
    async def fail(value: int) -> int:
        await asyncio.sleep(0)
        if value == 2:
            raise RuntimeError("boom")
        return value

    with pytest.raises(RuntimeError, match="boom"):
        await bounded_map(list(range(10)), fail, limit=3)


async def test_bounded_map_validates_limit_even_for_empty_input() -> None:
    async def identity(value: int) -> int:
        return value

    with pytest.raises(ValueError, match="positive"):
        await bounded_map([], identity, limit=0)
