"""Hummingbot compatibility layer for liquidations-feed.

Provides drop-in replacements for:
- LiquidationsFactory (hummingbot.data_feed.liquidations_feed.liquidations_factory)
- LiquidationsConfig (hummingbot.data_feed.liquidations_feed.liquidations_factory)
- LiquidationsBase (hummingbot.data_feed.liquidations_feed.liquidations_base)
"""

from liquidations_feed.hb_compat.factory import LiquidationsConfig, LiquidationsFactory

__all__ = [
    "LiquidationsFactory",
    "LiquidationsConfig",
]
