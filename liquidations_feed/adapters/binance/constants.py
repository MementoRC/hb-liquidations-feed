"""Binance Perpetual Futures liquidation constants."""

from liquidations_feed.core.throttler import LinkedLimitWeightPair, RateLimit

REST_URL = "https://fapi.binance.com"
HEALTH_CHECK_ENDPOINT = "/fapi/v1/ping"
EXCHANGE_INFO_ENDPOINT = "/fapi/v1/exchangeInfo"
# Throttler limit ids deliberately mirror hummingbot's binance_perpetual_constants (PING_URL,
# EXCHANGE_INFO_URL) so an injected host AsyncThrottler applies its own limits.
HEALTH_CHECK_LIMIT_ID = "v1/ping"
EXCHANGE_INFO_LIMIT_ID = "v1/exchangeInfo"
# Combined-stream route: every frame is wrapped as {"stream": ..., "data": {...}}.
WSS_URL = "wss://fstream.binance.com/market/stream"

REQUEST_WEIGHT = "REQUEST_WEIGHT"

# Source: Binance USDS-M Futures docs,
# https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
# ("Limits" section): REQUEST_WEIGHT is 2400 per minute per IP. Values were cross-checked
# against hummingbot's in-tree binance_perpetual connector (REQUEST_WEIGHT 2400/min, ping
# weight 1, exchangeInfo weight 40); the conservative exchangeInfo weight is taken from there.
# Each endpoint id is linked to the shared REQUEST_WEIGHT budget.
REQUEST_WEIGHT_LIMIT = 2400
REQUEST_WEIGHT_INTERVAL_SECONDS = 60
PING_WEIGHT = 1
EXCHANGE_INFO_WEIGHT = 40

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, REQUEST_WEIGHT_LIMIT, REQUEST_WEIGHT_INTERVAL_SECONDS),
    RateLimit(
        HEALTH_CHECK_LIMIT_ID,
        REQUEST_WEIGHT_LIMIT,
        REQUEST_WEIGHT_INTERVAL_SECONDS,
        linked_limits=(LinkedLimitWeightPair(REQUEST_WEIGHT, PING_WEIGHT),),
    ),
    RateLimit(
        EXCHANGE_INFO_LIMIT_ID,
        REQUEST_WEIGHT_LIMIT,
        REQUEST_WEIGHT_INTERVAL_SECONDS,
        linked_limits=(LinkedLimitWeightPair(REQUEST_WEIGHT, EXCHANGE_INFO_WEIGHT),),
    ),
]
