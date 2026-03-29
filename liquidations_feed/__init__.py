"""Liquidations Feed - Real-time liquidation data from cryptocurrency exchanges."""

from liquidations_feed.__about__ import __version__
from liquidations_feed.adapters.binance import BinancePerpetualAdapter
from liquidations_feed.core.adapter_base import BaseAdapter
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.core.liquidations_feed import LiquidationsFeed
from liquidations_feed.core.network_client import NetworkClient

__all__ = [
    "BaseAdapter",
    "BinancePerpetualAdapter",
    "Liquidation",
    "LiquidationSide",
    "LiquidationsFeed",
    "NetworkClient",
    "__version__",
]
