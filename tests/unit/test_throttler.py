"""AsyncThrottler: sliding-window limits, linked limits, and ThrottlerProtocol conformance."""

import pytest

from liquidations_feed.adapters.binance import constants
from liquidations_feed.core.protocols import ThrottlerProtocol
from liquidations_feed.core.throttler import AsyncThrottler, LinkedLimitWeightPair, RateLimit


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _throttler(limits, fake):
    return AsyncThrottler(limits, clock=fake.clock, sleep=fake.sleep)


async def test_calls_within_limit_do_not_wait():
    fake = FakeTime()
    throttler = _throttler([RateLimit("a", 3, 10)], fake)
    for _ in range(3):
        async with throttler.execute_task("a"):
            pass
    assert fake.sleeps == []


async def test_call_over_limit_waits_until_oldest_expires():
    fake = FakeTime()
    throttler = _throttler([RateLimit("a", 2, 10)], fake)
    async with throttler.execute_task("a"):
        pass
    fake.now = 4.0
    async with throttler.execute_task("a"):
        pass
    async with throttler.execute_task("a"):
        pass
    assert fake.sleeps == [6.0]
    assert fake.now == 10.0


async def test_weight_is_charged_against_the_limit():
    fake = FakeTime()
    throttler = _throttler([RateLimit("a", 5, 10)], fake)
    async with throttler.execute_task("a", weight=5):
        pass
    async with throttler.execute_task("a", weight=1):
        pass
    assert fake.sleeps == [10.0]


async def test_linked_limit_is_shared_between_endpoints():
    fake = FakeTime()
    shared = LinkedLimitWeightPair("pool", 1)
    throttler = _throttler(
        [
            RateLimit("pool", 2, 10),
            RateLimit("x", 100, 10, linked_limits=(shared,)),
            RateLimit("y", 100, 10, linked_limits=(shared,)),
        ],
        fake,
    )
    async with throttler.execute_task("x"):
        pass
    async with throttler.execute_task("y"):
        pass
    assert fake.sleeps == []
    async with throttler.execute_task("x"):
        pass
    assert fake.sleeps == [10.0]


async def test_unknown_limit_id_raises():
    throttler = AsyncThrottler([RateLimit("a", 1, 1)])
    with pytest.raises(ValueError, match="Unknown rate limit id"):
        async with throttler.execute_task("nope"):
            pass


async def test_weight_above_limit_raises_instead_of_hanging():
    throttler = AsyncThrottler([RateLimit("a", 1, 1)])
    with pytest.raises(ValueError, match="exceeds the limit"):
        async with throttler.execute_task("a", weight=2):
            pass


def test_throttler_satisfies_protocol():
    assert isinstance(AsyncThrottler([]), ThrottlerProtocol)


def test_binance_limits_are_registered_and_linked_to_request_weight():
    ids = {rl.limit_id for rl in constants.RATE_LIMITS}
    assert {
        constants.REQUEST_WEIGHT,
        constants.HEALTH_CHECK_ENDPOINT,
        constants.EXCHANGE_INFO_ENDPOINT,
    } <= ids
    for rl in constants.RATE_LIMITS:
        if rl.limit_id != constants.REQUEST_WEIGHT:
            assert [p.limit_id for p in rl.linked_limits] == [constants.REQUEST_WEIGHT]
    weights = {
        rl.limit_id: rl.linked_limits[0].weight
        for rl in constants.RATE_LIMITS
        if rl.limit_id != constants.REQUEST_WEIGHT
    }
    assert weights == {
        constants.HEALTH_CHECK_ENDPOINT: 1,
        constants.EXCHANGE_INFO_ENDPOINT: 40,
    }
