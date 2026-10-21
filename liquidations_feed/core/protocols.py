"""Protocol definitions for liquidations feed components."""

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ThrottlerProtocol(Protocol):
    """Rate limiter a host may inject (hummingbot's ``AsyncThrottler`` satisfies it).

    ``limit_id`` values are the adapter's ``rate_limits`` ids, so an injected throttler must be
    configured with those limits.
    """

    def execute_task(self, limit_id: str) -> AbstractAsyncContextManager[None]: ...


@runtime_checkable
class NetworkClientProtocol(Protocol):
    async def ws_connect(self, url: str) -> "WSAssistantProtocol": ...
    async def rest_get(
        self, url: str, params: dict | None = None, limit_id: str | None = None
    ) -> Any: ...
    async def close(self) -> None: ...


@runtime_checkable
class WSAssistantProtocol(Protocol):
    async def send(self, payload: Any) -> None: ...
    async def disconnect(self) -> None: ...
    def iter_messages(self) -> AsyncGenerator[Any, None]: ...
