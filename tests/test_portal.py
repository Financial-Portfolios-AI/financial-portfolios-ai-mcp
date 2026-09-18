"""Portal reads: what is retried, what is cached, and who a cache entry belongs to."""

import asyncio
import logging
from unittest.mock import patch

import httpx
import pytest
from financial_portfolios_ai.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.auth import reset_request_token, set_request_token


@pytest.fixture(autouse=True)
def _no_sleeping():
    """Backoff waits are real seconds; skip them."""
    with patch("financial_portfolios_ai_mcp.portal.asyncio.sleep", new=_noop_sleep):
        yield


async def _noop_sleep(_seconds):
    return None


def _failing_then(value, *errors):
    calls = {"n": 0}

    async def operation():
        calls["n"] += 1
        if calls["n"] <= len(errors):
            raise errors[calls["n"] - 1]
        return value

    return operation, calls


# --------------------------------------------------------------------------- #
# Retry
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        APIError("bad gateway", 502),
        APIError("unavailable", 503),
        APIError("gateway timeout", 504),
        APIError("server error", 500),
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("too slow"),
    ],
)
async def test_transient_failures_are_retried(error):
    operation, calls = _failing_then({"ok": True}, error)
    assert await portal.with_retry(operation, what="test") == {"ok": True}
    assert calls["n"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("no", 401),
        AuthenticationError("nope", 403),
        NotFoundError("gone", 404),
        ValidationError("bad", 422),
        RateLimitError("slow down", 429),
    ],
)
async def test_client_errors_are_not_retried(error):
    """A 4xx is an answer; retrying only delays the user."""
    operation, calls = _failing_then({"ok": True}, error)
    with pytest.raises(type(error)):
        await portal.with_retry(operation, what="test")
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_retries_are_bounded_and_then_raise(caplog):
    error = APIError("bad gateway", 502)
    operation, calls = _failing_then({"ok": True}, error, error, error, error)
    with caplog.at_level(logging.WARNING, logger="financial_portfolios_ai_mcp.portal"), pytest.raises(APIError):
        await portal.with_retry(operation, what="list_portfolios")
    assert calls["n"] == 3  # the default: one attempt plus two retries
    retries = [r for r in caplog.records if r.getMessage() == "portal_retry"]
    assert [r.attempt for r in retries] == [1, 2]
    assert retries[0].operation == "list_portfolios"


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_repeat_reads_come_from_the_cache():
    operation, calls = _failing_then({"portfolios": []})
    first = await portal.read("list_portfolios", 60, operation)
    second = await portal.read("list_portfolios", 60, operation)
    assert first == second == {"portfolios": []}
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_a_cached_read_is_never_served_to_another_credential():
    """The portal answers differently per credential - a subscriber sees the live book
    where another user sees the delayed one - so the credential is part of the key."""
    subscriber, subscriber_calls = _failing_then({"access": "subscribed"})
    ctx = set_request_token("aqat_v1_subscriber")
    try:
        assert await portal.read("get_portfolio_allocation", 60, subscriber, code="AQA_DEFENSIVE") == {"access": "subscribed"}
    finally:
        reset_request_token(ctx)

    other, other_calls = _failing_then({"access": "public_delayed"})
    ctx = set_request_token("aqat_v1_someone_else")
    try:
        assert await portal.read("get_portfolio_allocation", 60, other, code="AQA_DEFENSIVE") == {"access": "public_delayed"}
    finally:
        reset_request_token(ctx)

    assert subscriber_calls["n"] == 1 and other_calls["n"] == 1


def test_cache_keys_hash_the_credential_and_never_contain_it():
    ctx = set_request_token("aqat_v1_secret_value")
    try:
        key = portal.cache_key("list_portfolios")
    finally:
        reset_request_token(ctx)
    assert "aqat_v1_secret_value" not in key
    assert "secret" not in key


@pytest.mark.asyncio
async def test_different_parameters_are_different_entries():
    defensive, defensive_calls = _failing_then({"code": "AQA_DEFENSIVE"})
    balanced, balanced_calls = _failing_then({"code": "AQA_BALANCED"})
    await portal.read("get_portfolio_allocation", 60, defensive, code="AQA_DEFENSIVE")
    await portal.read("get_portfolio_allocation", 60, balanced, code="AQA_BALANCED")
    assert defensive_calls["n"] == 1 and balanced_calls["n"] == 1


@pytest.mark.asyncio
async def test_zero_ttl_disables_the_cache():
    operation, calls = _failing_then({"ok": True})
    await portal.read("list_portfolios", 0, operation)
    await portal.read("list_portfolios", 0, operation)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_entries_expire():
    """Rewind the entry's expiry rather than sleeping: the no-sleep fixture patches
    asyncio.sleep itself, so a real wait here would not happen either."""
    operation, calls = _failing_then({"ok": True})
    await portal.read("list_portfolios", 60, operation)
    key = portal.cache_key("list_portfolios")
    expires_at, value = portal._cache._entries[key]
    portal._cache._entries[key] = (expires_at - 61, value)

    await portal.read("list_portfolios", 60, operation)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_concurrent_reads_of_one_key_share_a_single_fetch():
    """The Explorer's stock search reads every portfolio at once."""
    calls = {"n": 0}

    async def slow():
        calls["n"] += 1
        await asyncio.sleep(0.02)
        return {"ok": True}

    results = await asyncio.gather(*(portal.read("list_portfolios", 60, slow) for _ in range(5)))
    assert results == [{"ok": True}] * 5
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cache_is_bounded():
    for i in range(portal.MAX_CACHE_ENTRIES + 25):
        operation, _ = _failing_then({"i": i})
        await portal.read("get_portfolio_allocation", 60, operation, code=f"CODE_{i}")
    assert portal.cache_stats()["entries"] <= portal.MAX_CACHE_ENTRIES
