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

__all__ = ["get_logger"]


def get_logger(name: str) -> HummingbotLogger:
    """Return a module-level :class:`HummingbotLogger` for ``name``."""
    return logging.getLogger(name)  # type: ignore[return-value]
