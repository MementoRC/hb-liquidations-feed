"""Binance Perpetual Futures liquidation constants."""

REST_URL = "https://fapi.binance.com"
HEALTH_CHECK_ENDPOINT = "/fapi/v1/ping"
EXCHANGE_INFO_ENDPOINT = "/fapi/v1/exchangeInfo"
# Combined-stream route: every frame is wrapped as {"stream": ..., "data": {...}}.
WSS_URL = "wss://fstream.binance.com/market/stream"
