"""Synchronous ``LiquidationsBase``-compatible wrapper around the async core feed.

Upstream consumers call ``start()``/``stop()`` synchronously from inside a running event loop
and poll ``ready`` and ``liquidations_df()``. The core ``LiquidationsFeed`` keeps its async
lifecycle; this wrapper schedules the coroutines as tasks and never creates an event loop.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from liquidations_feed.hb_compat.common import get_logger

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    import pandas as pd

    from liquidations_feed.core.liquidations_feed import LiquidationsFeed

logger = get_logger(__name__)


class LiquidationsBase:
    """Wraps a core feed and exposes the upstream ``LiquidationsBase`` public API."""

    def __init__(self, feed: LiquidationsFeed):
        self._feed = feed
        self._tasks: set[asyncio.Task[None]] = set()
        self._start_task: asyncio.Task[None] | None = None
        self._started = False

    @property
    def feed(self) -> LiquidationsFeed:
        return self._feed

    @property
    def name(self) -> str:
        return self._feed.name

    @property
    def trading_pairs(self) -> set[str]:
        return self._feed.trading_pairs

    @property
    def ready(self) -> bool:
        """True only once the core ``start()`` has completed successfully."""
        return self._started

    def liquidations_df(self, trading_pair: str | None = None) -> pd.DataFrame:
        return self._feed.liquidations_df(trading_pair)

    def start(self) -> None:
        """Schedule the core ``start()``; requires a running event loop. No-op if pending/running."""
        loop = self._running_loop("start")
        if self._started or (self._start_task is not None and not self._start_task.done()):
            return
        self._start_task = self._schedule(loop, self._feed.start(), "start")

    def stop(self) -> None:
        """Cancel any pending start and schedule the core ``stop()``; requires a running loop."""
        loop = self._running_loop("stop")
        if self._start_task is not None and not self._start_task.done():
            self._start_task.cancel()
        self._start_task = None
        self._started = False
        self._schedule(loop, self._feed.stop(), "stop")

    @staticmethod
    def _running_loop(action: str) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            msg = f"LiquidationsBase.{action}() requires a running event loop; call it from async code"
            raise RuntimeError(msg) from None

    def _schedule(
        self, loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, None], action: str
    ) -> asyncio.Task[None]:
        task = loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._on_done(t, action))
        return task

    def _on_done(self, task: asyncio.Task[None], action: str) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(f"Liquidations feed {action}() failed: {exc!r}", exc_info=exc)
        elif action == "start" and task is self._start_task:
            self._started = True
