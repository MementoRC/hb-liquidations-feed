"""Throttled REST calls and check_network, from the network client up to the hb_compat wrapper."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses

from liquidations_feed.adapters.binance import BinancePerpetualAdapter, constants
from liquidations_feed.core.liquidations_feed import LiquidationsFeed
from liquidations_feed.core.network_client import NetworkClient
from liquidations_feed.core.throttler import AsyncThrottler
from liquidations_feed.hb_compat import LiquidationsBase, NetworkStatus

PING_URL = f"{constants.REST_URL}{constants.HEALTH_CHECK_ENDPOINT}"


class RecordingThrottler:
    def __init__(self):
        self.calls: list[str] = []

    @asynccontextmanager
    async def execute_task(self, limit_id, weight=None):
        self.calls.append(limit_id)
        yield


async def test_rest_get_uses_throttler_when_limit_id_given():
    throttler = RecordingThrottler()
    client = NetworkClient(throttler=throttler)
    with aioresponses() as mocked:
        mocked.get(PING_URL, payload={})
        await client.rest_get(PING_URL, limit_id="ping")
    await client.close()
    assert throttler.calls == ["ping"]


async def test_rest_get_without_limit_id_is_not_throttled():
    throttler = RecordingThrottler()
    client = NetworkClient(throttler=throttler)
    with aioresponses() as mocked:
        mocked.get(PING_URL, payload={})
        await client.rest_get(PING_URL)
    await client.close()
    assert throttler.calls == []


async def test_rest_get_raises_on_http_error_status():
    client = NetworkClient()
    with aioresponses() as mocked:
        mocked.get(PING_URL, status=429, payload={"code": -1003})
        with pytest.raises(aiohttp.ClientResponseError):
            await client.rest_get(PING_URL)
    await client.close()


async def test_exchange_info_fetch_is_throttled_under_its_endpoint_id():
    adapter = BinancePerpetualAdapter()
    client = MagicMock()
    client.rest_get = AsyncMock(return_value={"symbols": []})
    await adapter.fetch_trading_pair_map(client)
    assert client.rest_get.await_args.kwargs["limit_id"] == constants.EXCHANGE_INFO_ENDPOINT


def test_binance_adapter_exposes_health_check_and_limits():
    adapter = BinancePerpetualAdapter()
    assert adapter.health_check_url == PING_URL
    assert adapter.health_check_limit_id == constants.HEALTH_CHECK_ENDPOINT
    assert adapter.rate_limits is constants.RATE_LIMITS


def test_feed_builds_default_client_with_adapter_throttler():
    feed = LiquidationsFeed(adapter=BinancePerpetualAdapter())
    assert isinstance(feed._network_client._throttler, AsyncThrottler)


def test_feed_uses_injected_throttler():
    throttler = RecordingThrottler()
    feed = LiquidationsFeed(adapter=BinancePerpetualAdapter(), throttler=throttler)
    assert feed._network_client._throttler is throttler


def _feed_with_client(client):
    return LiquidationsFeed(adapter=BinancePerpetualAdapter(), network_client=client)


async def test_feed_check_network_pings_health_endpoint_with_limit_id():
    client = AsyncMock()
    assert await _feed_with_client(client).check_network() is True
    client.rest_get.assert_awaited_once_with(PING_URL, limit_id=constants.HEALTH_CHECK_ENDPOINT)


async def test_feed_check_network_false_on_failure():
    client = AsyncMock()
    client.rest_get.side_effect = ConnectionError("down")
    assert await _feed_with_client(client).check_network() is False


async def test_feed_check_network_propagates_cancellation():
    client = AsyncMock()
    client.rest_get.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await _feed_with_client(client).check_network()


async def test_feed_check_network_does_not_require_start():
    feed = _feed_with_client(AsyncMock())
    assert feed._active is False
    assert await feed.check_network() is True


async def test_compat_check_network_connected():
    base = LiquidationsBase(_feed_with_client(AsyncMock()))
    assert await base.check_network() is NetworkStatus.CONNECTED


async def test_compat_check_network_not_connected_on_failure():
    client = AsyncMock()
    client.rest_get.side_effect = TimeoutError()
    base = LiquidationsBase(_feed_with_client(client))
    assert await base.check_network() is NetworkStatus.NOT_CONNECTED


def test_network_status_matches_hummingbot_values():
    assert [(s.name, s.value) for s in NetworkStatus] == [
        ("STOPPED", 0),
        ("NOT_CONNECTED", 1),
        ("CONNECTED", 2),
    ]
