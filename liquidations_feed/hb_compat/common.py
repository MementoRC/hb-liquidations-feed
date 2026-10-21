"""Logging compatibility shim — isolates the ``hb-logger`` dependency.

Internal call sites obtain module-level loggers via :func:`get_logger`
instead of importing the standard-library ``logging`` module directly.
Importing this module registers :class:`logger.HummingbotLogger` as the
default logger class (mirroring the ``hb-logger`` README usage pattern),
so every logger returned here carries the ``notify``/``network`` extensions
without callers needing a ``# type: ignore[assignment]`` at each call site.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import logger as _logger  # noqa: F401  (import registers HummingbotLogger as the default class)

if TYPE_CHECKING:
    from logger import HummingbotLogger

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["get_logger", "liquidations_df_with_ms", "seconds_to_ms"]


def get_logger(name: str) -> HummingbotLogger:
    """Return a module-level :class:`HummingbotLogger` for ``name``."""
    return logging.getLogger(name)  # type: ignore[return-value]


def seconds_to_ms(timestamp: float) -> int:
    """Convert core float epoch seconds to upstream's int epoch milliseconds."""
    return round(timestamp * 1000)


def liquidations_df_with_ms(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a core liquidations frame with ``timestamp`` as int ms.

    Upstream ``LiquidationsBase.liquidations_df`` exposes ``timestamp`` as int
    milliseconds; the core keeps float seconds, so the wrapper applies this.
    """
    out = df.copy()
    out["timestamp"] = [seconds_to_ms(ts) for ts in df["timestamp"]]
    out["timestamp"] = out["timestamp"].astype("int64")
    return out
