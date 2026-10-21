"""Unit tests for BinancePerpetualAdapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from liquidations_feed.adapters.binance import constants
from liquidations_feed.adapters.binance.adapter import BinancePerpetualAdapter
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide


def _make_adapter():
    return BinancePerpetualAdapter()


def _make_force_order_event(
    symbol="BTCUSDT",
    side="SELL",
    price="30000.0",
    quantity="0.5",
    timestamp=1_700_000_000_000,
    avg_price=None,
    pair=None,
):
    """Build a forceOrder frame as delivered by the combined stream: {"stream", "data"}."""
    return {
        "stream": "!forceOrder@arr",
        "data": {
            "e": "forceOrder",
            "E": timestamp,
            "o": {
                "s": symbol,
                "pair": pair if pair is not None else symbol,
                "S": side,
                "o": "LIMIT",
                "f": "IOC",
                "q": quantity,
                "p": price,
                "ap": avg_price if avg_price is not None else price,
                "X": "FILLED",
                "l": quantity,
                "z": quantity,
                "T": timestamp,
            },
        },
    }


class TestBinancePerpetualAdapterProperties:
    def test_name(self):
        adapter = _make_adapter()
        assert adapter.name == "binance_perpetual"

    def test_wss_url_is_market_stream_endpoint(self):
        assert constants.WSS_URL == "wss://fstream.binance.com/market/stream"

    def test_wss_url(self):
        adapter = _make_adapter()
        assert adapter.wss_url == constants.WSS_URL
        assert "binance" in adapter.wss_url.lower()

    def test_rest_url(self):
        adapter = _make_adapter()
        assert adapter.rest_url == constants.REST_URL
        assert "binance" in adapter.rest_url.lower()


class TestBinancePerpetualAdapterSubscribe:
    async def test_subscribe_all_pairs(self):
        adapter = _make_adapter()
        ws = AsyncMock()

        await adapter.subscribe(ws, set())

        ws.send.assert_called_once()
        call_args = ws.send.call_args[0][0]
        assert call_args["method"] == "SUBSCRIBE"
        assert "!forceOrder@arr" in call_args["params"]

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
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
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

        assert trading_pair == "BTC-USDT"
        assert liquidation.side is LiquidationSide.LONG
        assert liquidation.price == 30_000.0
        assert liquidation.quantity == 0.5
        assert liquidation.timestamp == pytest.approx(1_700_000_000.0, rel=1e-6)

    def test_process_message_short_liquidation(self):
        """BUY side on Binance means a SHORT position was liquidated."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"ETHUSDT": "ETH-USDT"}
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

    def test_process_message_uses_average_price(self):
        """The liquidation price is the average price 'ap', not the order price 'p'."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        msg = _make_force_order_event(price="30000.0", avg_price="29950.5")
        adapter.process_message(msg, feed)

        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert liquidation.price == 29_950.5

    def test_process_message_maps_pair_field_not_symbol(self):
        """Delivery contract symbol 's' resolves through the 'pair' field."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        msg = _make_force_order_event(symbol="BTCUSDT_241227", pair="BTCUSDT")
        adapter.process_message(msg, feed)

        assert feed.add_liquidation.call_args[0][0] == "BTC-USDT"


class TestBinancePerpetualAdapterUnmappedSymbols:
    def test_delivery_symbol_without_pair_is_dropped_and_logged(self, caplog):
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()
        msg = _make_force_order_event(symbol="BTCUSDT_251226")
        del msg["data"]["o"]["pair"]

        with caplog.at_level("DEBUG"):
            adapter.process_message(msg, feed)

        feed.add_liquidation.assert_not_called()
        assert "BTCUSDT_251226" in caplog.text

    def test_symbol_not_in_populated_map_is_dropped(self):
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        adapter.process_message(_make_force_order_event(symbol="ETHUSDT"), feed)

        feed.add_liquidation.assert_not_called()


def _symbol_info(symbol, pair, base="BTC", quote="USDT"):
    return {"symbol": symbol, "pair": pair, "baseAsset": base, "quoteAsset": quote}


class TestBinancePerpetualAdapterFetchTradingPairMap:
    async def test_keys_by_pair_field(self):
        adapter = _make_adapter()
        client = MagicMock()
        client.rest_get = AsyncMock(return_value={"symbols": [_symbol_info("BTCUSDT", "BTCUSDT")]})

        mapping = await adapter.fetch_trading_pair_map(client)

        assert mapping == {"BTCUSDT": "BTC-USDT"}
        assert adapter._trading_pair_map == mapping

    async def test_delivery_contract_dedupe_prefers_expected_symbol(self):
        """Perpetual and delivery contract mapping to one pair resolve deterministically."""
        perp = _symbol_info("BTCUSDT", "BTCUSDT")
        delivery = _symbol_info("BTCUSDT_241227", "BTCUSDT_241227")
        for symbols in ([perp, delivery], [delivery, perp]):
            adapter = _make_adapter()
            client = MagicMock()
            client.rest_get = AsyncMock(return_value={"symbols": symbols})

            mapping = await adapter.fetch_trading_pair_map(client)

            assert mapping == {"BTCUSDT": "BTC-USDT"}

    async def test_unresolvable_duplicate_removes_pair(self):
        adapter = _make_adapter()
        client = MagicMock()
        client.rest_get = AsyncMock(
            return_value={
                "symbols": [
                    _symbol_info("BTCUSDT_241227", "BTCUSDT_241227"),
                    _symbol_info("BTCUSDT_250328", "BTCUSDT_250328"),
                ]
            }
        )

        mapping = await adapter.fetch_trading_pair_map(client)

        assert mapping == {}

    async def test_reverse_lookup_uses_deduped_map(self):
        adapter = _make_adapter()
        client = MagicMock()
        client.rest_get = AsyncMock(
            return_value={
                "symbols": [
                    _symbol_info("BTCUSDT_241227", "BTCUSDT_241227"),
                    _symbol_info("BTCUSDT", "BTCUSDT"),
                ]
            }
        )
        await adapter.fetch_trading_pair_map(client)

        assert adapter._get_exchange_pair("BTC-USDT") == "BTCUSDT"


class TestBinancePerpetualAdapterProcessMessageInvalid:
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

    def test_unwrapped_frame_is_ignored(self):
        """/market/stream always wraps payloads; a bare event is not a shape it delivers."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        adapter.process_message(_make_force_order_event()["data"], feed)

        feed.add_liquidation.assert_not_called()

    def test_subscribe_ack_is_ignored(self):
        adapter = _make_adapter()
        feed = MagicMock()

        adapter.process_message({"result": None, "id": 1}, feed)

        feed.add_liquidation.assert_not_called()

    def test_wrapped_frame_is_unwrapped(self):
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        adapter.process_message(_make_force_order_event(), feed)

        feed.add_liquidation.assert_called_once()

    def test_timestamp_is_float_seconds_from_ms_t(self):
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        adapter.process_message(_make_force_order_event(timestamp=1_700_000_000_123), feed)

        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert isinstance(liquidation.timestamp, float)
        assert liquidation.timestamp == pytest.approx(1_700_000_000.123, abs=1e-6)

    def test_process_message_empty_dict(self):
        """Empty dict is silently ignored."""
        adapter = _make_adapter()
        feed = MagicMock()

        adapter.process_message({}, feed)

        feed.add_liquidation.assert_not_called()

    def test_process_message_timestamp_conversion(self):
        """Timestamp should be converted from milliseconds to seconds."""
        adapter = _make_adapter()
        adapter._trading_pair_map = {"BTCUSDT": "BTC-USDT"}
        feed = MagicMock()

        ts_ms = 1_700_000_000_123
        msg = _make_force_order_event(timestamp=ts_ms)
        adapter.process_message(msg, feed)

        liquidation: Liquidation = feed.add_liquidation.call_args[0][1]
        assert liquidation.timestamp == pytest.approx(ts_ms / 1000.0, rel=1e-9)
