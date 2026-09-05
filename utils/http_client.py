import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

_client: httpx.AsyncClient | None = None
_semaphore: asyncio.Semaphore | None = None
_yahoo_semaphore: asyncio.Semaphore | None = None
_sec_semaphore: asyncio.Semaphore | None = None
_sheets_semaphore: asyncio.Semaphore | None = None
_binance_semaphore: asyncio.Semaphore | None = None


def get_outbound_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(25)
    return _semaphore


def get_yahoo_semaphore() -> asyncio.Semaphore:
    global _yahoo_semaphore
    if _yahoo_semaphore is None:
        _yahoo_semaphore = asyncio.Semaphore(25)
    return _yahoo_semaphore


def get_sec_semaphore() -> asyncio.Semaphore:
    global _sec_semaphore
    if _sec_semaphore is None:
        _sec_semaphore = asyncio.Semaphore(10)
    return _sec_semaphore


def get_sheets_semaphore() -> asyncio.Semaphore:
    global _sheets_semaphore
    if _sheets_semaphore is None:
        _sheets_semaphore = asyncio.Semaphore(5)
    return _sheets_semaphore


def get_binance_semaphore() -> asyncio.Semaphore:
    global _binance_semaphore
    if _binance_semaphore is None:
        _binance_semaphore = asyncio.Semaphore(5)
    return _binance_semaphore


def _create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(15.0, connect=5.0),
        limits=httpx.Limits(max_connections=150, max_keepalive_connections=40, keepalive_expiry=60.0),
        headers={"User-Agent": "Mozilla/5.0"},
    )


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = _create_http_client()
    return _client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _client, _semaphore, _yahoo_semaphore, _sec_semaphore, _sheets_semaphore, _binance_semaphore
    _client = _create_http_client()
    _semaphore = asyncio.Semaphore(25)
    _yahoo_semaphore = asyncio.Semaphore(25)
    _sec_semaphore = asyncio.Semaphore(10)
    _sheets_semaphore = asyncio.Semaphore(5)
    _binance_semaphore = asyncio.Semaphore(5)
    yield
    if _client:
        await _client.aclose()
        _client = None

