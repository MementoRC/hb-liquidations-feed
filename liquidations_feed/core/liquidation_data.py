"""Liquidation data types."""

import enum
from dataclasses import dataclass, fields

import pandas as pd


class LiquidationSide(enum.Enum):
    SHORT = "SHORT"
    LONG = "LONG"

    def __str__(self):
        return self.value


@dataclass
class Liquidation:
    """A single liquidation event.

    ``timestamp`` is float epoch **seconds** (comparable with ``time.time()``).
    Upstream's hb_compat contract uses int milliseconds; convert with
    ``liquidations_feed.hb_compat.common.seconds_to_ms`` at that boundary only.
    """

    timestamp: float
    trading_pair: str
    quantity: float
    price: float
    side: LiquidationSide
