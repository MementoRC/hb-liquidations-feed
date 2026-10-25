"""REST rate limiting, backed by ``hb-rate-limit`` (import name ``rate_limit``).

This module keeps the historical names: ``RateLimit`` and ``LinkedLimitWeightPair`` are
re-exported unchanged, and ``AsyncThrottler`` is ``rate_limit.RateLimiter`` with the positional
``(rate_limits, clock, sleep)`` constructor.

``AsyncThrottler.execute_task`` mirrors the call shape of hummingbot's ``AsyncThrottler`` so a
host may inject its own throttler (see ``ThrottlerProtocol``) configured with the same limit ids.

An unknown limit id raises ``UnknownRateLimitError`` (a ``KeyError``); a weight above its limit
raises ``RateLimitWeightError`` (a ``ValueError``) before any wait.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable

from rate_limit import (
    LinkedLimitWeightPair,
    RateLimit,
    RateLimiter,
    RateLimitLike,
    RateLimitWeightError,
    UnknownRateLimitError,
)

__all__ = [
    "AsyncThrottler",
    "LinkedLimitWeightPair",
    "RateLimit",
    "RateLimitWeightError",
    "UnknownRateLimitError",
]


class AsyncThrottler(RateLimiter):
    """Sliding-window throttler: ``execute_task`` waits until every involved limit has room."""

    def __init__(
        self,
        rate_limits: Iterable[RateLimitLike],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        super().__init__(rate_limits, clock=clock, sleep=sleep)
