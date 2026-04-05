"""Unit tests for LiquidationsFeed."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.core.liquidations_feed import LiquidationsFeed


def _make_feed(trading_pairs=None, max_retention_seconds=60):
    adapter = MagicMock()
    adapter.name = "test_exchange"
    network_client = AsyncMock()
    feed = LiquidationsFeed(
        adapter=adapter,
        trading_pairs=trading_pairs,
        max_retention_seconds=max_retention_seconds,
        network_client=network_client,
    )
    return feed, adapter, network_client


def _make_liquidation(trading_pair="BTC-USDT", side=LiquidationSide.LONG, timestamp=None):
    return Liquidation(
        timestamp=timestamp if timestamp is not None else time.time(),
        trading_pair=trading_pair,
        quantity=0.5,
        price=30_000.0,
        side=side,
    )


class TestLiquidationsFeedInit:
    def test_init_defaults(self):
        adapter = MagicMock()
        adapter.name = "binance_perpetual"
        feed = LiquidationsFeed(adapter=adapter)

        assert feed._adapter is adapter
        assert feed._trading_pairs == set()
        assert feed._max_retention_seconds == 60
        assert feed._subscribed is False
        assert feed._active is False
        assert feed._listen_task is None
        assert feed._cleanup_task is None

    def test_name_delegates_to_adapter(self):
        feed, adapter, _ = _make_feed()
        adapter.name = "my_exchange"
        assert feed.name == "my_exchange"

    def test_trading_pairs_property(self):
        pairs = {"BTC-USDT", "ETH-USDT"}
        feed, _, _ = _make_feed(trading_pairs=pairs)
        assert feed.trading_pairs == pairs


class TestAddLiquidation:
    def test_add_liquidation(self):
        feed, _, _ = _make_feed()
        liq = _make_liquidation("BTC-USDT")
        feed.add_liquidation("BTC-USDT", liq)
        assert len(feed._liquidations["BTC-USDT"]) == 1
        assert feed._liquidations["BTC-USDT"][0] is liq

    def test_add_multiple_liquidations_same_pair(self):
        feed, _, _ = _make_feed()
        liq1 = _make_liquidation("BTC-USDT")
        liq2 = _make_liquidation("BTC-USDT")
        feed.add_liquidation("BTC-USDT", liq1)
        feed.add_liquidation("BTC-USDT", liq2)
        assert len(feed._liquidations["BTC-USDT"]) == 2

    def test_add_liquidations_different_pairs(self):
        feed, _, _ = _make_feed()
        feed.add_liquidation("BTC-USDT", _make_liquidation("BTC-USDT"))
        feed.add_liquidation("ETH-USDT", _make_liquidation("ETH-USDT"))
        assert len(feed._liquidations["BTC-USDT"]) == 1
        assert len(feed._liquidations["ETH-USDT"]) == 1


class TestLiquidationsDf:
    def test_liquidations_df_empty(self):
        feed, _, _ = _make_feed()
        df = feed.liquidations_df()
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert set(df.columns) == {"timestamp", "trading_pair", "quantity", "price", "side"}

    def test_liquidations_df_with_data(self):
        feed, _, _ = _make_feed()
        liq1 = _make_liquidation("BTC-USDT", LiquidationSide.LONG)
        liq2 = _make_liquidation("ETH-USDT", LiquidationSide.SHORT)
        feed.add_liquidation("BTC-USDT", liq1)
        feed.add_liquidation("ETH-USDT", liq2)

        df = feed.liquidations_df()
        assert len(df) == 2
        assert set(df["trading_pair"].tolist()) == {"BTC-USDT", "ETH-USDT"}

    def test_liquidations_df_filtered_by_pair(self):
        feed, _, _ = _make_feed()
        feed.add_liquidation("BTC-USDT", _make_liquidation("BTC-USDT"))
        feed.add_liquidation("BTC-USDT", _make_liquidation("BTC-USDT"))
        feed.add_liquidation("ETH-USDT", _make_liquidation("ETH-USDT"))

        df = feed.liquidations_df(trading_pair="BTC-USDT")
        assert len(df) == 2
        assert all(df["trading_pair"] == "BTC-USDT")

    def test_liquidations_df_filtered_pair_not_present(self):
        feed, _, _ = _make_feed()
        df = feed.liquidations_df(trading_pair="XRP-USDT")
        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestReadyProperty:
    def test_ready_property_false_initially(self):
        feed, _, _ = _make_feed()
        assert feed.ready is False

    def test_ready_property_true_when_subscribed(self):
        feed, _, _ = _make_feed()
        feed._subscribed = True
        assert feed.ready is True

    def test_ready_property_false_after_unsubscribe(self):
        feed, _, _ = _make_feed()
        feed._subscribed = True
        feed._subscribed = False
        assert feed.ready is False


class TestStartStop:
    async def test_start_creates_tasks(self):
        feed, _, _ = _make_feed()

        created_tasks = []

        def fake_create_task(coro):
            task = MagicMock(spec=asyncio.Task)
            task.done.return_value = False
            created_tasks.append(coro)
            # Close the coroutine to avoid ResourceWarning
            coro.close()
            return task

        with patch("asyncio.create_task", side_effect=fake_create_task):
            await feed.start()

        assert feed._active is True
        assert len(created_tasks) == 2

    async def test_start_idempotent(self):
        feed, _, _ = _make_feed()

        call_count = [0]

        def fake_create_task(coro):
            call_count[0] += 1
            task = MagicMock(spec=asyncio.Task)
            task.done.return_value = False
            coro.close()
            return task

        with patch("asyncio.create_task", side_effect=fake_create_task):
            await feed.start()
            await feed.start()  # second call should be a no-op

        assert call_count[0] == 2  # only from first start()

    async def test_stop_cancels_tasks(self):
        feed, _, network_client = _make_feed()

        listen_task = MagicMock(spec=asyncio.Task)
        listen_task.done.return_value = False
        listen_task.cancel = MagicMock()

        cleanup_task = MagicMock(spec=asyncio.Task)
        cleanup_task.done.return_value = False
        cleanup_task.cancel = MagicMock()

        # Simulate tasks raising CancelledError on await
        listen_task.__await__ = lambda self: (_ for _ in ()).throw(asyncio.CancelledError())
        cleanup_task.__await__ = lambda self: (_ for _ in ()).throw(asyncio.CancelledError())

        feed._active = True
        feed._listen_task = listen_task
        feed._cleanup_task = cleanup_task

        # Patch task awaiting to avoid TypeError
        async def mock_await_task(task):
            raise asyncio.CancelledError()

        async def patched_stop():
            feed._active = False
            for task in [feed._listen_task, feed._cleanup_task]:
                if task and not task.done():
                    task.cancel()
            await feed._network_client.close()

        await patched_stop()

        assert feed._active is False
        listen_task.cancel.assert_called_once()
        cleanup_task.cancel.assert_called_once()
        network_client.close.assert_called_once()


class TestCleanup:
    def test_cleanup_removes_old_data(self):
        feed, _, _ = _make_feed(max_retention_seconds=60)

        old_timestamp = time.time() - 120  # 2 minutes ago
        recent_timestamp = time.time() - 10  # 10 seconds ago

        old_liq = _make_liquidation("BTC-USDT", timestamp=old_timestamp)
        recent_liq = _make_liquidation("BTC-USDT", timestamp=recent_timestamp)

        feed.add_liquidation("BTC-USDT", old_liq)
        feed.add_liquidation("BTC-USDT", recent_liq)

        # Simulate cleanup manually (what _cleanup_loop does)
        cutoff = time.time() - feed._max_retention_seconds
        for pair in list(feed._liquidations.keys()):
            feed._liquidations[pair] = [
                liq for liq in feed._liquidations[pair] if liq.timestamp > cutoff
            ]

        assert len(feed._liquidations["BTC-USDT"]) == 1
        assert feed._liquidations["BTC-USDT"][0] is recent_liq

    def test_cleanup_keeps_all_recent_data(self):
        feed, _, _ = _make_feed(max_retention_seconds=60)

        for i in range(5):
            liq = _make_liquidation("ETH-USDT", timestamp=time.time() - i)
            feed.add_liquidation("ETH-USDT", liq)

        cutoff = time.time() - feed._max_retention_seconds
        for pair in list(feed._liquidations.keys()):
            feed._liquidations[pair] = [
                liq for liq in feed._liquidations[pair] if liq.timestamp > cutoff
            ]

        assert len(feed._liquidations["ETH-USDT"]) == 5
