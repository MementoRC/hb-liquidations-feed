"""Binance Perpetual Futures liquidation adapter."""

from typing import TYPE_CHECKING, Any, override

from liquidations_feed.adapters.binance import constants
from liquidations_feed.core.adapter_base import BaseAdapter
from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.core.throttler import RateLimit
from liquidations_feed.hb_compat.common import get_logger

if TYPE_CHECKING:
    from liquidations_feed.core.liquidations_feed import LiquidationsFeed
    from liquidations_feed.core.protocols import WSAssistantProtocol

logger = get_logger(__name__)


class BinancePerpetualAdapter(BaseAdapter):
    def __init__(self):
        self._trading_pair_map: dict = {}

    @override
    @property
    def name(self) -> str:
        return "binance_perpetual"

    @override
    @property
    def wss_url(self) -> str:
        return constants.WSS_URL

    @override
    @property
    def rest_url(self) -> str:
        return constants.REST_URL

    @override
    @property
    def health_check_url(self) -> str:
        return f"{constants.REST_URL}{constants.HEALTH_CHECK_ENDPOINT}"

    @override
    @property
    def health_check_limit_id(self) -> str:
        return constants.HEALTH_CHECK_LIMIT_ID

    @override
    @property
    def rate_limits(self) -> list[RateLimit]:
        return constants.RATE_LIMITS

    @override
    async def subscribe(self, ws: "WSAssistantProtocol", trading_pairs: set[str]) -> None:
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

    @override
    def process_message(self, msg: Any, feed: "LiquidationsFeed") -> None:
        if not isinstance(msg, dict):
            return

        # /market/stream wraps every event as {"stream": ..., "data": {...}}.
        # Subscribe acks ({"result": null, "id": 1}) carry no "data" and are skipped.
        payload = msg.get("data")
        if not isinstance(payload, dict):
            return
        event = payload.get("o")
        if not isinstance(event, dict):
            return

        try:
            exchange_pair = event.get("pair") or event.get("s", "")
            trading_pair = self._trading_pair_map.get(exchange_pair)
            if trading_pair is None:
                logger.debug(f"Dropping liquidation for unmapped symbol {exchange_pair!r}")
                return

            side_str = event.get("S", "")
            # SELL means a long position was liquidated, BUY means a short was liquidated
            side = LiquidationSide.LONG if side_str == "SELL" else LiquidationSide.SHORT

            # Binance "T" is epoch ms; the core stores float epoch seconds.
            liquidation = Liquidation(
                timestamp=float(event.get("T", 0)) / 1000.0,
                trading_pair=trading_pair,
                quantity=float(event.get("q", 0)),
                price=float(event.get("ap", 0)),
                side=side,
            )
            feed.add_liquidation(trading_pair, liquidation)
        except (KeyError, ValueError) as e:
            logger.error(f"Error processing liquidation message: {e}")

    @override
    async def fetch_trading_pair_map(self, network_client) -> dict:
        url = f"{self.rest_url}{constants.EXCHANGE_INFO_ENDPOINT}"
        data = await network_client.rest_get(url, limit_id=constants.EXCHANGE_INFO_LIMIT_ID)
        mapping: dict[str, str] = {}
        for symbol_info in data.get("symbols", []):
            exchange_symbol = symbol_info["pair"]
            base = symbol_info["baseAsset"]
            quote = symbol_info["quoteAsset"]
            hb_pair = f"{base}-{quote}"
            if hb_pair in mapping.values():
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = hb_pair
        self._trading_pair_map = mapping
        return mapping

    @staticmethod
    def _resolve_trading_pair_symbols_duplicate(
        mapping: dict[str, str], new_exchange_symbol: str, base: str, quote: str
    ) -> None:
        """Resolve name conflicts caused by delivery contracts.

        The BASEQUOTE exchange symbol wins if it is one of the two candidates;
        otherwise the pair is dropped from the map.
        """
        expected_exchange_symbol = f"{base}{quote}"
        hb_pair = f"{base}-{quote}"
        current_exchange_symbol = next(k for k, v in mapping.items() if v == hb_pair)
        if current_exchange_symbol == expected_exchange_symbol:
            return
        mapping.pop(current_exchange_symbol)
        if new_exchange_symbol == expected_exchange_symbol:
            mapping[new_exchange_symbol] = hb_pair
        else:
            logger.warning(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}"
            )

    def _get_exchange_pair(self, trading_pair: str) -> str | None:
        # Reverse lookup
        for exchange, hb in self._trading_pair_map.items():
            if hb == trading_pair:
                return exchange
        # Fallback: remove dash
        return trading_pair.replace("-", "")
