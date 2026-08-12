import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

_client: httpx.AsyncClient | None = None
_semaphore: asyncio.Semaphore | None = None


def get_outbound_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(10)
    return _semaphore


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    return _client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _client, _semaphore
    _client = httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    _semaphore = asyncio.Semaphore(10)
    yield
    if _client:
        await _client.aclose()
        _client = None
