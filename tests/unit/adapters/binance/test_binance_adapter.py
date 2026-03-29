"""Unit tests for BinancePerpetualAdapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from liquidations_feed.adapters.binance.adapter import BinancePerpetualAdapter
from liquidations_feed.adapters.binance import constants
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide


def _make_adapter():
    return BinancePerpetualAdapter()


def _make_force_order_event(
    symbol="BTCUSDT",
    side="SELL",
    price="30000.0",
    quantity="0.5",
    timestamp=1_700_000_000_000,
):
    """Build a forceOrder message in Binance WebSocket format."""
    return {
        "e": "forceOrder",
        "E": timestamp,
        "o": {
            "s": symbol,
            "S": side,
            "o": "LIMIT",
            "f": "IOC",
            "q": quantity,
            "p": price,
            "ap": price,
            "X": "FILLED",
            "l": quantity,
            "z": quantity,
            "T": timestamp,
        },
    }


class TestBinancePerpetualAdapterProperties:
    def test_name(self):
        adapter = _make_adapter()
        assert adapter.name == "binance_perpetual"

    def test_wss_url(self):
        adapter = _make_adapter()
        assert adapter.wss_url == constants.WSS_URL
        assert "binance" in adapter.wss_url.lower()

    def test_rest_url(self):
        adapter = _make_adapter()
        assert adapter.rest_url == constants.REST_URL
        assert "binance" in adapter.rest_url.lower()


class TestBinancePerpetualAdapterSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_all_pairs(self):
        adapter = _make_adapter()
        ws = AsyncMock()

        await adapter.subscribe(ws, set())

        ws.send.assert_called_once()
        call_args = ws.send.call_args[0][0]
        assert call_args["method"] == "SUBSCRIBE"
        assert "!forceOrder@arr" in call_args["params"]

    @pytest.mark.asyncio
    async def test_subscribe_specific_pairs(self):
        adapter = _make_adapter()
        ws = AsyncMock()

        # Populate the trading pair map so subscribe can look up pairs
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"}
        await adapter.subscribe(ws, {"BTC-USDT", "ETH-USDT"})

        ws.send.assert_called_once()
        call_args = ws.send.call_args[0][0]
        assert call_args["method"] == "SUBSCRIBE"
        params = call_args["params"]
        assert any("btcusdt" in p for p in params)
        assert any("ethusdt" in p for p in params)
        assert all("@forceOrder" in p for p in params)

    @pytest.mark.asyncio
    async def test_subscribe_specific_pairs_fallback(self):
        """When trading pair map is empty, falls back to removing dash."""
        adapter = _make_adapter()
        ws = AsyncMock()

        await adapter.subscribe(ws, {"BTC-USDT"})

        ws.send.assert_called_once()
        call_args = ws.send.call_args[0][0]
        params = call_args["params"]
        assert any("btcusdt" in p for p in params)


class TestBinancePerpetualAdapterProcessMessage:
    def test_process_message_long_liquidation(self):
        """SELL side on Binance means a LONG position was liquidated."""
        adapter = _make_adapter()
        feed = MagicMock()

        msg = _make_force_order_event(
            symbol="BTCUSDT",
            side="SELL",
            price="30000.0",
            quantity="0.5",
            timestamp=1_700_000_000_000,
        )
        adapter.process_message(msg, feed)

        feed.add_liquidation.assert_called_once()
        call_args = feed.add_liquidation.call_args
        trading_pair = call_args[0][0]
        liquidation: Liquidation = call_args[0][1]

        assert trading_pair == "BTCUSDT"
        assert liquidation.side is LiquidationSide.LONG
        assert liquidation.price == 30_000.0
        assert liquidation.quantity == 0.5
        assert liquidation.timestamp == pytest.approx(1_700_000_000.0, rel=1e-6)

    def test_process_message_short_liquidation(self):
        """BUY side on Binance means a SHORT position was liquidated."""
        adapter = _make_adapter()
        feed = MagicMock()

        msg = _make_force_order_event(
            symbol="ETHUSDT",
            side="BUY",
            price="2000.0",
            quantity="1.0",
            timestamp=1_700_000_001_000,
        )
        adapter.process_message(msg, feed)

        feed.add_liquidation.assert_called_once()
        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert liquidation.side is LiquidationSide.SHORT
        assert liquidation.price == 2_000.0

    def test_process_message_with_trading_pair_map(self):
        """When a trading pair map exists, it should be used for mapping."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        msg = _make_force_order_event(symbol="BTCUSDT", side="SELL")
        adapter.process_message(msg, feed)

        feed.add_liquidation.assert_called_once()
        trading_pair = feed.add_liquidation.call_args[0][0]
        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert trading_pair == "BTC-USDT"
        assert liquidation.trading_pair == "BTC-USDT"

    def test_process_message_invalid_data_non_dict(self):
        """Non-dict messages are silently ignored."""
        adapter = _make_adapter()
        feed = MagicMock()

        adapter.process_message("not a dict", feed)
        adapter.process_message(None, feed)
        adapter.process_message(["list"], feed)

        feed.add_liquidation.assert_not_called()

    def test_process_message_missing_o_key(self):
        """Messages without 'o' key and without forceOrder event are ignored."""
        adapter = _make_adapter()
        feed = MagicMock()

        adapter.process_message({"e": "trade", "data": {}}, feed)

        feed.add_liquidation.assert_not_called()

    def test_process_message_empty_dict(self):
        """Empty dict is silently ignored."""
        adapter = _make_adapter()
        feed = MagicMock()

        adapter.process_message({}, feed)

        feed.add_liquidation.assert_not_called()

    def test_process_message_timestamp_conversion(self):
        """Timestamp should be converted from milliseconds to seconds."""
        adapter = _make_adapter()
        feed = MagicMock()

        ts_ms = 1_700_000_000_123
        msg = _make_force_order_event(timestamp=ts_ms)
        adapter.process_message(msg, feed)

        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert liquidation.timestamp == pytest.approx(ts_ms / 1000.0, rel=1e-9)
