"""Main liquidations feed orchestrator."""

import asyncio
import contextlib
import random
import time
from collections import defaultdict
from collections.abc import Callable

import pandas as pd

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide, fields
from liquidations_feed.core.network_client import NetworkClient
from liquidations_feed.core.protocols import NetworkClientProtocol, ThrottlerProtocol
from liquidations_feed.core.throttler import AsyncThrottler
from liquidations_feed.hb_compat.common import get_logger

logger = get_logger(__name__)


class LiquidationsFeed:
    """Real-time liquidation data feed from cryptocurrency exchanges.

    Standalone implementation that works with or without hummingbot.
    """

    def __init__(
        self,
        adapter,
        trading_pairs: set[str] | None = None,
        max_retention_seconds: int = 60,
        network_client: NetworkClientProtocol | None = None,
        cleanup_interval_seconds: float | None = None,
        reconnect_delay_seconds: float = 1.0,
        reconnect_max_delay_seconds: float = 30.0,
        rng: Callable[[float, float], float] = random.uniform,
        throttler: ThrottlerProtocol | None = None,
    ):
        """``throttler`` paces the default network client's REST calls (default: an
        ``AsyncThrottler`` built from ``adapter.rate_limits``). It is ignored when a custom
        ``network_client`` is supplied, which then owns its own rate limiting.
        """
        self._adapter = adapter
        self._trading_pairs = trading_pairs or set()
        self._max_retention_seconds = max_retention_seconds
        self._network_client = network_client or NetworkClient(
            throttler=throttler or AsyncThrottler(adapter.rate_limits)
        )
        self._cleanup_interval_seconds = (
            cleanup_interval_seconds
            if cleanup_interval_seconds is not None
            else max_retention_seconds / 2
        )
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._reconnect_max_delay_seconds = reconnect_max_delay_seconds
        self._rng = rng
        self._liquidations: dict[str, list[Liquidation]] = defaultdict(list)
        self._listen_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._subscribed: bool = False
        self._active: bool = False

    @property
    def name(self) -> str:
        return self._adapter.name

    @property
    def ready(self) -> bool:
        return self._subscribed

    @property
    def trading_pairs(self) -> set[str]:
        return self._trading_pairs

    def add_liquidation(self, trading_pair: str, liquidation: Liquidation):
        self._liquidations[trading_pair].append(liquidation)

    def liquidations_df(self, trading_pair: str | None = None) -> pd.DataFrame:
        if trading_pair:
            data = self._liquidations.get(trading_pair, [])
        else:
            data = [liq for liq_list in self._liquidations.values() for liq in liq_list]
        cutoff = time.time() - self._max_retention_seconds
        data = [liq for liq in data if liq.timestamp > cutoff]
        if not data:
            return pd.DataFrame(columns=[f.name for f in fields(Liquidation)])
        return pd.DataFrame([vars(liq) for liq in data])

    async def check_network(self) -> bool:
        """Ping the exchange's REST health endpoint (rate limited).

        Returns True if it answered successfully and False on any failure; cancellation
        propagates.
        """
        try:
            await self._network_client.rest_get(
                self._adapter.health_check_url, limit_id=self._adapter.health_check_limit_id
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"{self.name} health check failed: {e!r}")
            return False
        return True

    async def start(self) -> None:
        if self._active:
            return
        pair_map = await self._adapter.fetch_trading_pair_map(self._network_client)
        if not pair_map:
            raise RuntimeError(
                f"{self.name}: fetched an empty trading-pair map; "
                "refusing to stream raw exchange symbols"
            )
        self._active = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Started {self.name} liquidations feed")

    async def stop(self) -> None:
        self._active = False
        for task in [self._listen_task, self._cleanup_task]:
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await self._network_client.close()
        logger.info(f"Stopped {self.name} liquidations feed")

    async def _listen_loop(self) -> None:
        attempt = 0
        while self._active:
            try:
                ws = await self._network_client.ws_connect(self._adapter.wss_url)
                try:
                    await self._adapter.subscribe(ws, self._trading_pairs)
                    self._subscribed = True
                    attempt = 0
                    async for msg in ws.iter_messages():
                        if not self._active:
                            break
                        self._adapter.process_message(msg, self)
                finally:
                    await ws.disconnect()
                    self._subscribed = False
            except asyncio.CancelledError:
                raise
            except ConnectionError as e:
                logger.warning(f"Connection error in liquidations listen loop: {e}")
                attempt = await self._backoff(attempt)
            except Exception as e:
                logger.error(f"Error in liquidations listen loop: {e}")
                attempt = await self._backoff(attempt)

    async def _backoff(self, attempt: int) -> int:
        """Sleep with exponential backoff and full jitter; return the next attempt number."""
        self._subscribed = False
        if self._active:
            cap = min(self._reconnect_max_delay_seconds, self._reconnect_delay_seconds * 2**attempt)
            await asyncio.sleep(self._rng(0, cap))
        return attempt + 1

    async def _cleanup_loop(self) -> None:
        while self._active:
            try:
                await asyncio.sleep(self._cleanup_interval_seconds)
                cutoff = time.time() - self._max_retention_seconds
                for pair in list(self._liquidations.keys()):
                    self._liquidations[pair] = [
                        liq for liq in self._liquidations[pair] if liq.timestamp > cutoff
                    ]
            except asyncio.CancelledError:
                raise
