"""Standalone sliding-window rate limiter (no hummingbot dependency).

``AsyncThrottler.execute_task`` mirrors the call shape of hummingbot's ``AsyncThrottler`` so a
host may inject its own throttler (see ``ThrottlerProtocol``) configured with the same limit ids.
"""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class LinkedLimitWeightPair:
    """Charges ``weight`` against the limit ``limit_id`` whenever the owning limit is used."""

    limit_id: str
    weight: int = 1


@dataclass(frozen=True)
class RateLimit:
    """At most ``limit`` weight may be consumed per ``time_interval`` seconds."""

    limit_id: str
    limit: int
    time_interval: float
    weight: int = 1
    linked_limits: tuple[LinkedLimitWeightPair, ...] = ()


class AsyncThrottler:
    """Sliding-window throttler: ``execute_task`` waits until every involved limit has room."""

    def __init__(
        self,
        rate_limits: Iterable[RateLimit],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._limits = {rl.limit_id: rl for rl in rate_limits}
        self._usage: dict[str, deque[tuple[float, int]]] = {lid: deque() for lid in self._limits}
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def execute_task(self, limit_id: str) -> AsyncIterator[None]:
        await self._acquire(limit_id)
        yield

    async def _acquire(self, limit_id: str) -> None:
        if limit_id not in self._limits:
            raise ValueError(f"Unknown rate limit id: {limit_id!r}")
        charges = [(limit_id, self._limits[limit_id].weight)]
        charges += [(p.limit_id, p.weight) for p in self._limits[limit_id].linked_limits]
        for lid, w in charges:
            if w > self._limits[lid].limit:
                raise ValueError(f"Weight {w} exceeds the limit of {lid!r}; it could never run")
        async with self._lock:
            while True:
                now = self._clock()
                wait = max(self._wait_for(lid, w, now) for lid, w in charges)
                if wait <= 0:
                    break
                await self._sleep(wait)
            for lid, w in charges:
                self._usage[lid].append((now, w))

    def _wait_for(self, limit_id: str, weight: int, now: float) -> float:
        """Seconds until ``weight`` fits in ``limit_id``'s window (0 if it fits now)."""
        limit = self._limits[limit_id]
        usage = self._usage[limit_id]
        while usage and usage[0][0] <= now - limit.time_interval:
            usage.popleft()
        excess = sum(w for _, w in usage) + weight - limit.limit
        for stamp, used in usage:
            if excess <= 0:
                break
            excess -= used
            if excess <= 0:
                return stamp + limit.time_interval - now
        return 0.0
