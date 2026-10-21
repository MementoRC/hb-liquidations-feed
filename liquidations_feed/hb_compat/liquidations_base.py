"""Legacy bridge: synchronous ``LiquidationsBase``-compatible wrapper around the async core feed.

Upstream consumers call ``start()``/``stop()`` synchronously (for example from a constructor)
and poll ``ready`` and ``liquidations_df()``. This wrapper schedules the coroutines as tasks and
never creates an event loop. A ``start()`` made with no running loop is deferred until the first
later access inside a running loop; that deferral exists only to bridge the legacy pattern.

The core ``LiquidationsFeed`` is async-only and is the supported API. New code should
``await feed.start()`` from an async lifecycle hook instead of starting I/O in a constructor.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from liquidations_feed.hb_compat.common import get_logger, liquidations_df_with_ms

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    import pandas as pd

    from liquidations_feed.core.liquidations_feed import LiquidationsFeed

logger = get_logger(__name__)


class LiquidationsBase:
    """Wraps a core feed and exposes the upstream ``LiquidationsBase`` public API.

    This is an hb_compat legacy bridge for consumers that call ``start()`` synchronously, for
    example from a constructor. The deferred start exists only to bridge that legacy pattern.
    The core ``LiquidationsFeed`` is async-only and is the supported API; new code should
    ``await feed.start()`` from an async lifecycle hook instead of starting I/O in a constructor.
    """

    def __init__(self, feed: LiquidationsFeed):
        self._feed = feed
        self._tasks: set[asyncio.Task[None]] = set()
        self._start_task: asyncio.Task[None] | None = None
        self._started = False
        self._pending_start = False

    @property
    def feed(self) -> LiquidationsFeed:
        self._maybe_start_pending()
        return self._feed

    @property
    def name(self) -> str:
        return self._feed.name

    @property
    def trading_pairs(self) -> set[str]:
        self._maybe_start_pending()
        return self._feed.trading_pairs

    @property
    def ready(self) -> bool:
        """True only once the core ``start()`` has completed successfully."""
        self._maybe_start_pending()
        return self._started

    def liquidations_df(self, trading_pair: str | None = None) -> pd.DataFrame:
        self._maybe_start_pending()
        return liquidations_df_with_ms(self._feed.liquidations_df(trading_pair))

    def start(self) -> None:
        """Schedule the core ``start()``. No-op if already pending or running.

        With no running event loop this does not raise: the start is recorded as pending and
        scheduled on the first later wrapper access made inside a running loop.
        """
        if self._pending_start:
            self._maybe_start_pending()
            return
        if self._started:
            return
        if self._start_task is not None and not self._start_task.done():
            return
        self._pending_start = True
        self._maybe_start_pending()
        if self._pending_start:
            logger.debug("No running event loop; liquidations feed start deferred")

    def stop(self) -> None:
        """Cancel any pending start and schedule the core ``stop()``.

        A start still waiting for a loop is just cleared (nothing to stop). Otherwise a
        running event loop is required.
        """
        if self._pending_start:
            self._pending_start = False
            return
        loop = self._running_loop("stop")
        if self._start_task is not None and not self._start_task.done():
            self._start_task.cancel()
        self._start_task = None
        self._started = False
        self._schedule(loop, self._feed.stop(), "stop")

    def _maybe_start_pending(self) -> None:
        """Schedule a deferred start, exactly once, if a loop is now running."""
        if not self._pending_start:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._pending_start = False
        self._start_task = self._schedule(loop, self._feed.start(), "start")

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
