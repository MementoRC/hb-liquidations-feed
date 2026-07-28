"""Unit tests for the hb-logger compatibility shim."""

import logging

from logger import HummingbotLogger

from liquidations_feed.hb_compat import get_logger
from liquidations_feed.hb_compat.common import get_logger as get_logger_direct


class TestGetLogger:
    def test_returns_hummingbot_logger_instance(self):
        log = get_logger(__name__)
        assert isinstance(log, HummingbotLogger)

    def test_registers_hummingbot_logger_as_default_class(self):
        assert logging.getLoggerClass() is HummingbotLogger

    def test_same_name_returns_same_logger(self):
        first = get_logger("liquidations_feed.hb_compat.test_common")
        second = get_logger("liquidations_feed.hb_compat.test_common")
        assert first is second

    def test_exported_from_package_and_module_are_identical(self):
        assert get_logger is get_logger_direct

    def test_call_sites_use_hummingbot_logger(self):
        from liquidations_feed.adapters.binance.adapter import logger as adapter_logger
        from liquidations_feed.core.liquidations_feed import logger as feed_logger
        from liquidations_feed.core.network_client import logger as network_logger

        assert isinstance(adapter_logger, HummingbotLogger)
        assert isinstance(feed_logger, HummingbotLogger)
        assert isinstance(network_logger, HummingbotLogger)
