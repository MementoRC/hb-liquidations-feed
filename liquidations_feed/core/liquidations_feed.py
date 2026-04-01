"""Main liquidations feed orchestrator."""

import asyncio
import contextlib
import logging
import time
from collections import defaultdict

import pandas as pd

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide, fields
from liquidations_feed.core.network_client import NetworkClient
from liquidations_feed.core.protocols import NetworkClientProtocol

logger = logging.getLogger(__name__)


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
    ):
        self._adapter = adapter
        self._trading_pairs = trading_pairs or set()
        self._max_retention_seconds = max_retention_seconds
        self._network_client = network_client or NetworkClient()
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
        if not data:
            return pd.DataFrame(columns=[f.name for f in fields(Liquidation)])
        return pd.DataFrame([vars(liq) for liq in data])

    async def start(self) -> None:
        if self._active:
            return
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
        while self._active:
            try:
                ws = await self._network_client.ws_connect(self._adapter.wss_url)
                try:
                    await self._adapter.subscribe(ws, self._trading_pairs)
                    self._subscribed = True
                    async for msg in ws.iter_messages():
                        if not self._active:
                            break
                        self._adapter.process_message(msg, self)
                finally:
                    await ws.disconnect()
                    self._subscribed = False
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in liquidations listen loop: {e}")
                self._subscribed = False
                if self._active:
                    await asyncio.sleep(5)

    async def _cleanup_loop(self) -> None:
        while self._active:
            try:
                await asyncio.sleep(self._max_retention_seconds / 2)
                cutoff = time.time() - self._max_retention_seconds
                for pair in list(self._liquidations.keys()):
                    self._liquidations[pair] = [
                        liq for liq in self._liquidations[pair] if liq.timestamp > cutoff
                    ]
            except asyncio.CancelledError:
                raise
