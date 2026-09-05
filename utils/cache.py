import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast

T = TypeVar("T")


class AsyncSingleflight:
    """Coalesces concurrent calls to the same async function by key."""

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def execute(self, key: str, fn: Callable[[], Coroutine[Any, Any, T]]) -> T:
        async with self._lock:
            if key in self._in_flight:
                task = self._in_flight[key]
            else:
                task = asyncio.create_task(fn())
                self._in_flight[key] = task

        try:
            res: T = cast(T, await task)
            return res
        finally:
            async with self._lock:
                if self._in_flight.get(key) is task:
                    del self._in_flight[key]

    def clear(self) -> None:
        self._in_flight.clear()


class TTLCache:
    """A lightweight in-memory cache with per-item TTL expiration and bounded capacity."""

    def __init__(self, default_ttl_seconds: float = 60.0, max_entries: int = 1000):
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries

    def get(self, key: str) -> Any | None:
        if key in self._store:
            expiry, value = self._store[key]
            if time.time() < expiry:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        now = time.time()
        expiry = now + (ttl if ttl is not None else self.default_ttl)

        if len(self._store) >= self.max_entries and key not in self._store:
            # Prune expired items
            expired = [k for k, (exp, _) in self._store.items() if now >= exp]
            for k in expired:
                del self._store[k]

            # If still at capacity, evict the entry with the earliest expiration
            if len(self._store) >= self.max_entries:
                earliest_key = min(self._store, key=lambda k: self._store[k][0])
                del self._store[earliest_key]

        self._store[key] = (expiry, value)

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def invalidate_prefix(self, prefix: str) -> None:
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]
        return len(self._store)


# Global cache & singleflight singletons
ttl_cache = TTLCache(default_ttl_seconds=60.0, max_entries=2000)
singleflight = AsyncSingleflight()
