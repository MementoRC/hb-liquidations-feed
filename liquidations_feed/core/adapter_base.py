"""Base adapter interface for exchange-specific liquidation feeds."""
from abc import ABC, abstractmethod
from typing import Any, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from liquidations_feed.core.liquidations_feed import LiquidationsFeed
    from liquidations_feed.core.protocols import WSAssistantProtocol


class BaseAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def wss_url(self) -> str: ...

    @property
    @abstractmethod
    def rest_url(self) -> str: ...

    @abstractmethod
    async def subscribe(self, ws: "WSAssistantProtocol", trading_pairs: Set[str]) -> None: ...

    @abstractmethod
    def process_message(self, msg: Any, feed: "LiquidationsFeed") -> None: ...

    @abstractmethod
    async def fetch_trading_pair_map(self, network_client) -> dict: ...
