"""Drop-in factory replacement matching hummingbot's LiquidationsFactory interface."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from liquidations_feed.core.liquidations_feed import LiquidationsFeed

# NOTE: adapter/feed imports below are deferred into get_liquidations_feed() rather than
# module scope. adapters.binance.adapter and core.liquidations_feed both import
# liquidations_feed.hb_compat.common (the logging shim), and hb_compat/__init__ imports this
# factory module — a module-scope import here would re-enter the partially initialized
# adapters/core modules and raise ImportError (circular import).
_SUPPORTED_CONNECTORS = ["binance"]


class UnsupportedConnectorError(Exception):
    def __init__(self, connector: str):
        super().__init__(
            f"Connector '{connector}' is not supported. Supported: {_SUPPORTED_CONNECTORS}"
        )


class LiquidationsConfig(BaseModel):
    connector: str
    trading_pairs: set[str] | None = None
    max_retention_seconds: int = 60


class LiquidationsFactory:
    @classmethod
    def get_liquidations_feed(cls, config: LiquidationsConfig) -> "LiquidationsFeed":
        from liquidations_feed.adapters.binance import BinancePerpetualAdapter
        from liquidations_feed.core.liquidations_feed import LiquidationsFeed

        connector_map = {"binance": BinancePerpetualAdapter}
        adapter_cls = connector_map.get(config.connector)
        if adapter_cls is None:
            raise UnsupportedConnectorError(config.connector)
        adapter = adapter_cls()
        return LiquidationsFeed(
            adapter=adapter,
            trading_pairs=config.trading_pairs,
            max_retention_seconds=config.max_retention_seconds,
        )
