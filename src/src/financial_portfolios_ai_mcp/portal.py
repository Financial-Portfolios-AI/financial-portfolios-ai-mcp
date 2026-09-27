"""Retry and per-credential caching for portal reads.

Two problems this solves:

* **Transient portal failures reached the user.** A single 502 or a dropped connection
  surfaced as a failed tool call. Idempotent reads are now retried with backoff.
* **Repeated identical reads.** The Portfolio Explorer fetches every portfolio for its
  search and comparison views, and each tab switch asked the portal again. Reads are
  cached briefly.

The cache key **always includes the caller's credential**, because what the portal returns
depends on it: a subscriber gets the latest book where another user gets the delayed one.
Keys hold a hash of the credential, never the credential itself. The cache is per process,
so an autoscaled deployment simply has several small caches.
"""

import asyncio
import hashlib
import logging
import random
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
from financial_portfolios_ai.exceptions import APIError

from financial_portfolios_ai_mcp.auth import resolve_api_token
from financial_portfolios_ai_mcp.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retried: the portal is up but a hop failed, or the connection did. Never 4xx - a 401,
# 403, 404, 422 or 429 is an answer, and retrying it only delays the user.
RETRY_STATUS = frozenset({500, 502, 503, 504})
RETRY_EXCEPTIONS = (httpx.TransportError, httpx.TimeoutException)

MAX_CACHE_ENTRIES = 512


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, RETRY_EXCEPTIONS):
        return True
    return isinstance(error, APIError) and error.status_code in RETRY_STATUS


async def with_retry(operation: Callable[[], Awaitable[T]], *, what: str) -> T:
    """Run `operation`, retrying transient failures with exponential backoff and jitter."""
    settings = get_settings()
    attempts = max(1, settings.portal_retries + 1)
    delay = settings.portal_retry_base_delay

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as error:
            if attempt == attempts or not _is_retryable(error):
                raise
            wait = delay * (2 ** (attempt - 1)) * (0.5 + random.random())
            logger.warning(
                "portal_retry",
                extra={"operation": what, "attempt": attempt, "of": attempts, "wait_s": round(wait, 3), "error": str(error)[:200]},
            )
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


class TTLCache:
    """Small LRU cache whose entries expire, holding one in-flight read per key.

    Concurrent callers asking for the same key await the same fetch rather than each
    hitting the portal - the Explorer's search fires several reads at once.
    """

    def __init__(self, max_entries: int = MAX_CACHE_ENTRIES) -> None:
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def _get(self, key: str) -> tuple[bool, Any]:
        entry = self._entries.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._entries[key]
            return False, None
        self._entries.move_to_end(key)
        return True, value

    def _set(self, key: str, value: Any, ttl: float) -> None:
        self._entries[key] = (time.monotonic() + ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    async def fetch(self, key: str, ttl: float, operation: Callable[[], Awaitable[T]]) -> T:
        if ttl <= 0:
            return await operation()
        found, value = self._get(key)
        if found:
            self.hits += 1
            return value  # type: ignore[no-any-return]
        task = self._inflight.get(key)
        if task is None:
            self.misses += 1
            task = asyncio.ensure_future(operation())
            self._inflight[key] = task
            try:
                value = await task
            finally:
                self._inflight.pop(key, None)
            self._set(key, value, ttl)
            return value  # type: ignore[no-any-return]
        return await asyncio.shield(task)  # type: ignore[no-any-return]

    def clear(self) -> None:
        self._entries.clear()


_cache = TTLCache()


def cache_key(operation: str, **params: Any) -> str:
    """A cache key bound to the caller's credential, which decides what the portal returns."""
    token = resolve_api_token() or "anonymous"
    identity = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    tail = ":".join(f"{k}={params[k]!r}" for k in sorted(params))
    return f"{identity}:{operation}:{tail}"


async def read(operation: str, ttl: float, fetch: Callable[[], Awaitable[T]], **params: Any) -> T:
    """Cached, retried portal read. `params` identify the read and form part of the key."""
    return await _cache.fetch(cache_key(operation, **params), ttl, lambda: with_retry(fetch, what=operation))


def cache_stats() -> dict[str, int]:
    return {"entries": len(_cache._entries), "hits": _cache.hits, "misses": _cache.misses}


def clear_cache() -> None:
    _cache.clear()
