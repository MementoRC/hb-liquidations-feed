"""Sync LiquidationsBase wrapper: lifecycle and accessor delegation."""

import asyncio
import logging

import pandas as pd
import pytest

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


def test_start_without_running_loop_raises_runtime_error():
    base = LiquidationsBase(FakeFeed())
    with pytest.raises(RuntimeError, match="running event loop"):
        base.start()
    assert base.ready is False


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


def test_factory_returns_wrapper():
    config = LiquidationsConfig(connector="binance", trading_pairs={"BTC-USDT"})
    base = LiquidationsFactory.get_liquidations_feed(config)
    assert isinstance(base, LiquidationsBase)
    assert base.trading_pairs == {"BTC-USDT"}
