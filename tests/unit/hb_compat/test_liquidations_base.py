"""Sync LiquidationsBase wrapper: lifecycle and accessor delegation."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from liquidations_feed.core.liquidations_feed import LiquidationsFeed
from liquidations_feed.hb_compat import LiquidationsBase, LiquidationsConfig, LiquidationsFactory


class FakeFeed:
    name = "fake"
    trading_pairs = {"BTC-USDT"}

    def __init__(self, start_error: Exception | None = None, stop_error: Exception | None = None):
        self.start_calls = 0
        self.stop_calls = 0
        self.start_error = start_error
        self.stop_error = stop_error
        self.start_gate = asyncio.Event()
        self.df_calls: list = []

    async def start(self):
        self.start_calls += 1
        await self.start_gate.wait()
        if self.start_error:
            raise self.start_error

    async def stop(self):
        self.stop_calls += 1
        if self.stop_error:
            raise self.stop_error

    def liquidations_df(self, trading_pair=None):
        self.df_calls.append(trading_pair)
        return pd.DataFrame({"pair": [trading_pair]})


async def _settle():
    for _ in range(3):
        await asyncio.sleep(0)


async def test_start_schedules_task_and_sets_ready_after_completion():
    feed = FakeFeed()
    base = LiquidationsBase(feed)
    assert base.ready is False

    base.start()
    await _settle()
    assert feed.start_calls == 1
    assert base.ready is False

    feed.start_gate.set()
    await _settle()
    assert base.ready is True


def test_start_without_running_loop_defers_without_raising_or_task():
    feed = FakeFeed()
    base = LiquidationsBase(feed)
    base.start()
    assert not base._tasks
    assert base._start_task is None
    assert feed.start_calls == 0


def test_later_ready_access_in_loop_starts_exactly_once():
    feed = FakeFeed()
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()

    async def scenario():
        assert base.ready is False
        assert base.ready is False
        await _settle()
        assert base.ready is True

    asyncio.run(scenario())
    assert feed.start_calls == 1


def test_stop_while_pending_means_never_starts():
    feed = FakeFeed()
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()
    base.stop()
    assert not base._tasks

    async def scenario():
        assert base.ready is False
        base.liquidations_df()
        await _settle()
        assert base.ready is False

    asyncio.run(scenario())
    assert feed.start_calls == 0
    assert feed.stop_calls == 0


def test_double_start_guard_in_pending_state():
    feed = FakeFeed()
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()
    base.start()

    async def scenario():
        base.start()
        base.start()
        await _settle()

    asyncio.run(scenario())
    assert feed.start_calls == 1


def test_pending_start_fires_from_liquidations_df():
    feed = FakeFeed()
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()

    async def scenario():
        base.liquidations_df()
        base.liquidations_df()
        await _settle()
        assert base.ready is True

    asyncio.run(scenario())
    assert feed.start_calls == 1


async def test_start_is_idempotent_while_pending_and_running():
    feed = FakeFeed()
    base = LiquidationsBase(feed)

    base.start()
    base.start()
    await _settle()
    assert feed.start_calls == 1

    feed.start_gate.set()
    await _settle()
    base.start()
    await _settle()
    assert feed.start_calls == 1


async def test_stop_cancels_pending_start_and_cleans_up():
    feed = FakeFeed()
    base = LiquidationsBase(feed)
    base.start()
    await _settle()

    base.stop()
    await _settle()

    assert feed.stop_calls == 1
    assert base.ready is False
    assert not base._tasks


async def test_stop_after_start_resets_ready():
    feed = FakeFeed()
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()
    await _settle()
    assert base.ready is True

    base.stop()
    await _settle()
    assert feed.stop_calls == 1
    assert base.ready is False
    assert not base._tasks


async def test_core_start_exception_is_logged_and_ready_stays_false(caplog):
    feed = FakeFeed(start_error=RuntimeError("empty pair map"))
    feed.start_gate.set()
    base = LiquidationsBase(feed)

    with caplog.at_level(logging.ERROR):
        base.start()
        await _settle()

    assert base.ready is False
    assert "empty pair map" in caplog.text


async def test_core_stop_exception_is_logged(caplog):
    feed = FakeFeed(stop_error=RuntimeError("close failed"))
    base = LiquidationsBase(feed)

    with caplog.at_level(logging.ERROR):
        base.stop()
        await _settle()

    assert "close failed" in caplog.text


async def test_start_can_be_retried_after_failure():
    feed = FakeFeed(start_error=RuntimeError("boom"))
    feed.start_gate.set()
    base = LiquidationsBase(feed)
    base.start()
    await _settle()

    feed.start_error = None
    base.start()
    await _settle()
    assert feed.start_calls == 2
    assert base.ready is True


def test_accessors_delegate():
    feed = FakeFeed()
    base = LiquidationsBase(feed)

    assert base.name == "fake"
    assert base.trading_pairs == {"BTC-USDT"}
    assert base.feed is feed
    base.liquidations_df()
    base.liquidations_df("BTC-USDT")
    assert feed.df_calls == [None, "BTC-USDT"]
    assert isinstance(base.liquidations_df("BTC-USDT"), pd.DataFrame)


def test_deferred_start_with_real_core_feed_empty_map_then_retry(caplog):
    adapter = MagicMock()
    adapter.name = "mock"
    adapter.fetch_trading_pair_map = AsyncMock(return_value={})
    network_client = MagicMock()
    network_client.close = AsyncMock()
    core = LiquidationsFeed(
        adapter=adapter, trading_pairs={"BTC-USDT"}, network_client=network_client
    )
    core._listen_loop = AsyncMock()
    core._cleanup_loop = AsyncMock()

    base = LiquidationsBase(core)
    base.start()
    assert not base._tasks

    async def scenario():
        with caplog.at_level(logging.ERROR):
            assert base.ready is False
            await _settle()
        assert base.ready is False
        assert "empty trading-pair map" in caplog.text

        adapter.fetch_trading_pair_map.return_value = {"BTCUSDT": "BTC-USDT"}
        base.start()
        await _settle()
        assert base.ready is True
        base.stop()
        await _settle()

    asyncio.run(scenario())
    assert adapter.fetch_trading_pair_map.await_count == 2


def test_factory_returns_wrapper():
    config = LiquidationsConfig(connector="binance", trading_pairs={"BTC-USDT"})
    base = LiquidationsFactory.get_liquidations_feed(config)
    assert isinstance(base, LiquidationsBase)
    assert base.trading_pairs == {"BTC-USDT"}
