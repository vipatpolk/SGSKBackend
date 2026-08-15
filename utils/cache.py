import time
from typing import Any


class TTLCache:
    """A lightweight in-memory cache with per-item TTL expiration."""

    def __init__(self, default_ttl_seconds: float = 60.0):
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        if key in self._store:
            expiry, value = self._store[key]
            if time.time() < expiry:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
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
        # Prune expired items on len check
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]
        return len(self._store)


# Global cache singletons
ttl_cache = TTLCache(default_ttl_seconds=60.0)
