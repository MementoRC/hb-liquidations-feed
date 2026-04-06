# hb-liquidations-feed

Real-time liquidation events feed for hummingbot.

## Overview

Streams liquidation events from exchanges via WebSocket, providing real-time visibility into market liquidations for use in trading strategies and risk management.

## Features

- Real-time liquidation event streaming
- Multi-exchange adapter support (Binance and more)
- Configurable event filtering
- Drop-in replacement for hummingbot via `hb_compat` layer

## Installation

```bash
pixi install
```

## Development

```bash
pixi run check    # lint + format + test
pixi run test     # run all tests
pixi run lint     # ruff check
pixi run format   # ruff format
```

## License

Apache-2.0 — see [LICENSE](LICENSE)
