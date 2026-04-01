"""Drop-in factory replacement matching hummingbot's LiquidationsFactory interface."""

from pydantic import BaseModel

from liquidations_feed.adapters.binance import BinancePerpetualAdapter
from liquidations_feed.core.liquidations_feed import LiquidationsFeed


class UnsupportedConnectorError(Exception):
    def __init__(self, connector: str):
        supported = list(_CONNECTOR_MAP.keys())
        super().__init__(f"Connector '{connector}' is not supported. Supported: {supported}")


class LiquidationsConfig(BaseModel):
    connector: str
    trading_pairs: set[str] | None = None
    max_retention_seconds: int = 60


_CONNECTOR_MAP = {
    "binance": BinancePerpetualAdapter,
}


class LiquidationsFactory:
    @classmethod
    def get_liquidations_feed(cls, config: LiquidationsConfig) -> LiquidationsFeed:
        adapter_cls = _CONNECTOR_MAP.get(config.connector)
        if adapter_cls is None:
            raise UnsupportedConnectorError(config.connector)
        adapter = adapter_cls()
        return LiquidationsFeed(
            adapter=adapter,
            trading_pairs=config.trading_pairs,
            max_retention_seconds=config.max_retention_seconds,
        )
