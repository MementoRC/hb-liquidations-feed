"""Unit tests for LiquidationsFactory and LiquidationsConfig."""

import pytest

from liquidations_feed.adapters.binance import BinancePerpetualAdapter
from liquidations_feed.core.liquidations_feed import LiquidationsFeed
from liquidations_feed.hb_compat.factory import (
    LiquidationsConfig,
    LiquidationsFactory,
    UnsupportedConnectorException,
)


class TestLiquidationsConfig:
    def test_config_defaults(self):
        config = LiquidationsConfig(connector="binance")
        assert config.connector == "binance"
        assert config.trading_pairs is None
        assert config.max_retention_seconds == 60

    def test_config_with_trading_pairs(self):
        pairs = {"BTC-USDT", "ETH-USDT"}
        config = LiquidationsConfig(connector="binance", trading_pairs=pairs)
        assert config.trading_pairs == pairs

    def test_config_custom_retention(self):
        config = LiquidationsConfig(connector="binance", max_retention_seconds=120)
        assert config.max_retention_seconds == 120


class TestLiquidationsFactory:
    def test_get_binance_feed(self):
        config = LiquidationsConfig(connector="binance")
        feed = LiquidationsFactory.get_liquidations_feed(config)

        assert isinstance(feed, LiquidationsFeed)
        assert isinstance(feed._adapter, BinancePerpetualAdapter)

    def test_get_binance_feed_with_trading_pairs(self):
        pairs = {"BTC-USDT", "ETH-USDT"}
        config = LiquidationsConfig(connector="binance", trading_pairs=pairs)
        feed = LiquidationsFactory.get_liquidations_feed(config)

        assert feed.trading_pairs == pairs

    def test_get_binance_feed_with_custom_retention(self):
        config = LiquidationsConfig(connector="binance", max_retention_seconds=300)
        feed = LiquidationsFactory.get_liquidations_feed(config)

        assert feed._max_retention_seconds == 300

    def test_unknown_connector_raises(self):
        config = LiquidationsConfig(connector="kraken")
        with pytest.raises(UnsupportedConnectorException) as exc_info:
            LiquidationsFactory.get_liquidations_feed(config)

        assert "kraken" in str(exc_info.value)
        assert "binance" in str(exc_info.value)

    def test_unsupported_connector_exception_message(self):
        exc = UnsupportedConnectorException("unknown_exchange")
        assert "unknown_exchange" in str(exc)
        assert "binance" in str(exc)

    def test_factory_is_classmethod(self):
        # Can be called on the class directly
        config = LiquidationsConfig(connector="binance")
        feed = LiquidationsFactory.get_liquidations_feed(config)
        assert isinstance(feed, LiquidationsFeed)
