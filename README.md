# hb-liquidations-feed

A modular liquidations data feed for cryptocurrency exchanges, designed as a standalone sub-package of the Hummingbot ecosystem.

## Overview

`hb-liquidations-feed` provides real-time liquidation event data from cryptocurrency exchanges via WebSocket streams. It supersedes the `hummingbot.data_feed.liquidations_feed` module and can be used as a drop-in replacement in Hummingbot, or independently in any Python application.

Liquidation events occur when a leveraged position is forcibly closed by an exchange. Monitoring these events is valuable for:
- Understanding market stress and volatility
- Identifying potential price impact from large liquidations
- Building trading strategies that respond to liquidation cascades

## Features

- Real-time liquidation data via WebSocket (forceOrder stream)
- Clean, typed data models using Pydantic
- Async-first design using aiohttp
- Drop-in Hummingbot compatibility via `hb_compat` layer
- Modular adapter architecture for easy exchange extension

## Supported Exchanges

| Exchange | Market Type | Stream |
|----------|-------------|--------|
| Binance  | Perpetual   | `!forceOrder@arr` (WebSocket) |

## Installation

```bash
# Using pip
pip install hb-liquidations-feed

# Using pixi
pixi add hb-liquidations-feed

# From source
git clone https://github.com/MementoRC/hb-liquidations-feed.git
cd hb-liquidations-feed
pixi run pytest --version  # Verify setup
```

## Quick Start

```python
import asyncio
from liquidations_feed import LiquidationsFeed

async def main():
    feed = LiquidationsFeed(
        trading_pair="BTC-USDT",
        connector_name="binance_perpetual",
    )

    await feed.start()

    # Access liquidation data
    async for liquidation in feed.liquidations():
        print(f"Liquidation: {liquidation.trading_pair} "
              f"side={liquidation.side} "
              f"quantity={liquidation.quantity} "
              f"price={liquidation.price}")

asyncio.run(main())
```

## Hummingbot Integration

When installed alongside Hummingbot, `hb-liquidations-feed` automatically replaces the built-in liquidations feed via the `hb_compat` compatibility layer:

```python
# In Hummingbot strategies, use exactly as before:
from hummingbot.data_feed.liquidations_feed import LiquidationsFeed

# The hb_compat layer transparently routes to this package
feed = LiquidationsFeed(trading_pair="BTC-USDT", connector_name="binance_perpetual")
```

The `hb_compat` module provides:
- `LiquidationsFeed` — drop-in replacement for hummingbot's built-in class
- `LiquidationsConfig` — compatible configuration dataclass

## Development Setup

This project uses [pixi](https://pixi.sh) for environment management.

```bash
# Clone the repository
git clone https://github.com/MementoRC/hb-liquidations-feed.git
cd hb-liquidations-feed

# Run tests
pixi run test-unit

# Run linting
pixi run lint

# Run all quality checks
pixi run quality

# Install pre-commit hooks
pixi run pre-commit install
```

### Available Tasks

| Task | Description |
|------|-------------|
| `pixi run test` | Run all tests |
| `pixi run test-unit` | Run unit tests only |
| `pixi run lint` | Run ruff linter |
| `pixi run format` | Auto-format code |
| `pixi run format-check` | Check formatting without changes |
| `pixi run quality` | Run lint + format check |
| `pixi run check` | Run quality + tests |

### Python Environments

The project supports Python 3.10, 3.11, and 3.12:

```bash
pixi run -e py310 test-unit
pixi run -e py311 test-unit
pixi run -e py312 test-unit
```

## Project Structure

```
liquidations_feed/
    __about__.py          # Version information
    __init__.py           # Public API
    core/                 # Core data models and feed logic
    adapters/             # Exchange-specific WebSocket adapters
        binance/          # Binance perpetual forceOrder adapter
    hb_compat/            # Hummingbot drop-in compatibility layer
tests/
    unit/                 # Unit tests
    integration/          # Integration tests (with mock servers)
```

## Adding Exchange Adapters

To add a new exchange adapter:

1. Create `liquidations_feed/adapters/your_exchange/` with:
   - `__init__.py`
   - `perpetual_adapter.py` — implements WebSocket subscription and message parsing
   - `constants.py` — exchange-specific constants

2. Implement the required interface:
   - `get_ws_subscription_payload(trading_pair)` — forceOrder stream subscription
   - `parse_ws_message(message)` — parse raw WebSocket message to `LiquidationData`

3. Register the adapter in `liquidations_feed/adapters/__init__.py`

4. Write unit and integration tests

## Architecture

The package follows a hexagonal architecture pattern:

- **Core**: Domain models (`LiquidationData`) and feed orchestration (`LiquidationsFeed`)
- **Adapters**: Exchange-specific WebSocket implementations (driven ports)
- **hb_compat**: Hummingbot compatibility façade (driving port)

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for development guidelines.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

## Related Projects

- [hb-candles-feed](https://github.com/MementoRC/hb-candles-feed) — Modular candles data feed (same architecture)
- [Hummingbot](https://github.com/hummingbot/hummingbot) — Open source crypto trading bot
