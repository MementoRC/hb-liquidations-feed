"""Hummingbot compatibility layer for liquidations-feed.

Provides drop-in replacements for:
- LiquidationsFactory, LiquidationsConfig, UnsupportedConnectorException
  (hummingbot.data_feed.liquidations_feed.liquidations_factory)
- Liquidation, LiquidationSide
  (hummingbot.data_feed.liquidations_feed.liquidations_base)

LiquidationsBase is not yet exported; the synchronous wrapper is tracked in issue #40.
"""

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.hb_compat.common import get_logger
from liquidations_feed.hb_compat.factory import (
    LiquidationsConfig,
    LiquidationsFactory,
    UnsupportedConnectorException,
)

__all__ = [
    "Liquidation",
    "LiquidationSide",
    "LiquidationsConfig",
    "LiquidationsFactory",
    "UnsupportedConnectorException",
    "get_logger",
]
