"""Binance Perpetual Futures liquidation adapter."""

import logging
from typing import Any, Set, TYPE_CHECKING

from liquidations_feed.adapters.binance import constants
from liquidations_feed.core.adapter_base import BaseAdapter
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide

if TYPE_CHECKING:
    from liquidations_feed.core.liquidations_feed import LiquidationsFeed
    from liquidations_feed.core.protocols import WSAssistantProtocol

logger = logging.getLogger(__name__)


class BinancePerpetualAdapter(BaseAdapter):
    def __init__(self):
        self._trading_pair_map: dict = {}

    @property
    def name(self) -> str:
        return "binance_perpetual"

    @property
    def wss_url(self) -> str:
        return constants.WSS_URL

    @property
    def rest_url(self) -> str:
        return constants.REST_URL

    async def subscribe(self, ws: "WSAssistantProtocol", trading_pairs: Set[str]) -> None:
        if not trading_pairs:
            # Subscribe to all liquidations
            await ws.send({"method": "SUBSCRIBE", "params": ["!forceOrder@arr"], "id": 1})
        else:
            # Subscribe to specific pairs
            streams = []
            for pair in trading_pairs:
                exchange_pair = self._get_exchange_pair(pair)
                if exchange_pair:
                    streams.append(f"{exchange_pair.lower()}@forceOrder")
            if streams:
                await ws.send({"method": "SUBSCRIBE", "params": streams, "id": 1})

    def process_message(self, msg: Any, feed: "LiquidationsFeed") -> None:
        if not isinstance(msg, dict):
            return

        # Handle array format (!forceOrder@arr)
        event = msg.get("o") if "o" in msg else None
        if event is None and msg.get("e") == "forceOrder":
            event = msg.get("o")
        if event is None:
            return

        try:
            exchange_pair = event.get("s", "")
            trading_pair = self._trading_pair_map.get(exchange_pair, exchange_pair)

            side_str = event.get("S", "")
            # SELL means a long position was liquidated, BUY means a short was liquidated
            side = LiquidationSide.LONG if side_str == "SELL" else LiquidationSide.SHORT

            liquidation = Liquidation(
                timestamp=float(event.get("T", 0)) / 1000.0,
                trading_pair=trading_pair,
                quantity=float(event.get("q", 0)),
                price=float(event.get("p", 0)),
                side=side,
            )
            feed.add_liquidation(trading_pair, liquidation)
        except (KeyError, ValueError) as e:
            logger.error(f"Error processing liquidation message: {e}")

    async def fetch_trading_pair_map(self, network_client) -> dict:
        url = f"{self.rest_url}{constants.EXCHANGE_INFO_ENDPOINT}"
        data = await network_client.rest_get(url)
        mapping = {}
        for symbol_info in data.get("symbols", []):
            exchange_symbol = symbol_info["symbol"]
            base = symbol_info["baseAsset"]
            quote = symbol_info["quoteAsset"]
            hb_pair = f"{base}-{quote}"
            mapping[exchange_symbol] = hb_pair
        self._trading_pair_map = mapping
        return mapping

    def _get_exchange_pair(self, trading_pair: str) -> str | None:
        # Reverse lookup
        for exchange, hb in self._trading_pair_map.items():
            if hb == trading_pair:
                return exchange
        # Fallback: remove dash
        return trading_pair.replace("-", "")
