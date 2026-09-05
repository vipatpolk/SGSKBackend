import asyncio

import pytest

from utils.cache import AsyncSingleflight, TTLCache


@pytest.mark.asyncio
async def test_async_singleflight_deduplication():
    flight = AsyncSingleflight()
    execution_count = 0

    async def worker():
        nonlocal execution_count
        execution_count += 1
        await asyncio.sleep(0.05)
        return "result"

    results = await asyncio.gather(
        flight.execute("test_key", worker),
        flight.execute("test_key", worker),
        flight.execute("test_key", worker),
    )

    assert results == ["result", "result", "result"]
    assert execution_count == 1


@pytest.mark.asyncio
async def test_async_singleflight_error_propagation():
    flight = AsyncSingleflight()

    async def failing_worker():
        await asyncio.sleep(0.02)
        raise ValueError("simulated error")

    with pytest.raises(ValueError, match="simulated error"):
        await asyncio.gather(
            flight.execute("fail_key", failing_worker),
            flight.execute("fail_key", failing_worker),
        )

    # After failure, subsequent call should re-execute
    async def ok_worker():
        return "ok"

    res = await flight.execute("fail_key", ok_worker)
    assert res == "ok"


def test_ttl_cache_capacity_and_eviction():
    cache = TTLCache(default_ttl_seconds=60.0, max_entries=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert len(cache) == 3

    # Add 4th item, oldest expiry should be evicted
    cache.set("d", 4)
    assert len(cache) == 3
    assert cache.get("d") == 4
