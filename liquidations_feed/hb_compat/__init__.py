"""Hummingbot compatibility layer for liquidations-feed.

Provides drop-in replacements for:
- LiquidationsFactory, LiquidationsConfig, UnsupportedConnectorException
  (hummingbot.data_feed.liquidations_feed.liquidations_factory)
- LiquidationsBase, Liquidation, LiquidationSide
  (hummingbot.data_feed.liquidations_feed.liquidations_base)

LiquidationsBase is a synchronous-lifecycle wrapper around the async core feed.
"""

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.hb_compat.common import get_logger
from liquidations_feed.hb_compat.factory import (
    LiquidationsConfig,
    LiquidationsFactory,
    UnsupportedConnectorException,
)
from liquidations_feed.hb_compat.liquidations_base import LiquidationsBase

__all__ = [
    "Liquidation",
    "LiquidationSide",
    "LiquidationsBase",
    "LiquidationsConfig",
    "LiquidationsFactory",
    "UnsupportedConnectorException",
    "get_logger",
]
