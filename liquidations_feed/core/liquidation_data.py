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
    timestamp: float
    trading_pair: str
    quantity: float
    price: float
    side: LiquidationSide
