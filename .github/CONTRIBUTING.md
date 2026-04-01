# Contributing to hb-liquidations-feed

Thank you for your interest in contributing to hb-liquidations-feed! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Either pixi, hatch, or uv package manager

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MementoRC/hb-liquidations-feed.git
   cd hb-liquidations-feed
   ```

2. **Set up development environment**:
   ```bash
   # Using pixi (recommended)
   pixi run pytest --version

   # Or using hatch
   hatch run dev:pytest --version
   ```

3. **Install pre-commit hooks**:
   ```bash
   pixi run pre-commit install
   ```

## Development Process

### Branch Strategy

- **main**: Production-ready code
- **development**: Main development branch for integration
- **feature/your-feature**: Feature development branches

### Workflow

1. **Create a feature branch**:
   ```bash
   git checkout development
   git pull origin development
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow coding standards (see below)
   - Write tests for new functionality
   - Update documentation as needed

3. **Run quality checks**:
   ```bash
   pixi run pytest                        # Run tests
   pixi run ruff check --select=F,E9      # Critical lint checks
   pixi run pre-commit run --all-files    # All hooks
   ```

4. **Commit your changes**:
   ```bash
   git add specific-files  # Be selective, don't use 'git add .'
   git commit -m "feat: add your feature description"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   # Create PR through GitHub interface
   ```

## Coding Standards

### Python Style Guidelines

- **Type annotations**: Use modern Python 3.12 syntax (`list[T]`, `dict[K, V]`, `T | None`)
- **Import organization**: Use relative imports within packages
- **Line length**: 88 characters (Black default)
- **Naming**: snake_case for variables/functions, PascalCase for classes

### Code Quality Requirements

- **Zero critical violations**: No F or E9 lint errors allowed
- **Test coverage**: All new code must include tests
- **Type safety**: Use proper type annotations
- **Documentation**: Include docstrings for public APIs

### Example Code Style

```python
from typing import Any
from .core import LiquidationData

def process_liquidations(
    liquidations: list[LiquidationData],
    trading_pair: str,
    *,
    validate: bool = True
) -> dict[str, Any]:
    """Process liquidation data for the specified trading pair.

    :param liquidations: List of liquidation data to process
    :param trading_pair: Trading pair for processing
    :param validate: Whether to validate input data
    :return: Processed liquidation data dictionary
    :raises ValueError: If liquidations data is invalid
    """
    if validate and not liquidations:
        raise ValueError("Liquidations list cannot be empty")

    return {
        "trading_pair": trading_pair,
        "count": len(liquidations),
        "processed": True
    }
```

## Testing Guidelines

### Test Organization

- **unit/**: Testing isolated components
- **integration/**: Testing component interactions
- **e2e/**: Testing complete workflows

### Writing Tests

```python
import pytest
from unittest.mock import patch, MagicMock

from liquidations_feed.adapters.binance import BinancePerpetualAdapter

class TestBinancePerpetualAdapter:
    def test_adapter_initialization(self):
        """Test adapter initializes correctly."""
        adapter = BinancePerpetualAdapter()
        assert adapter.exchange_name == "binance_perpetual"

    @patch('liquidations_feed.adapters.binance.aiohttp.ClientSession')
    async def test_ws_subscription(self, mock_session):
        """Test WebSocket subscription to forceOrder stream."""
        # Test implementation
        pass
```

### Running Tests

```bash
# Run all tests
pixi run test

# Run specific test types
pixi run test-unit
pixi run pytest tests/integration/

# Run with coverage
pixi run pytest --cov=liquidations_feed
```

## Documentation

### Code Documentation

- Use reStructuredText format for docstrings
- Document all public APIs
- Include examples for complex functionality
- Keep documentation up-to-date with code changes

## Security Considerations

### Security Best Practices

- **Never commit secrets**: Use environment variables for sensitive data
- **Validate inputs**: Sanitize all external inputs
- **Follow secure coding**: Use static analysis tools
- **Report vulnerabilities**: Use private vulnerability reporting

### Security Testing

All contributions are automatically scanned for:
- Secret detection
- Dependency vulnerabilities
- Code security issues (CodeQL)

## Exchange Adapter Development

### Adding New Exchange Adapters

1. **Create adapter structure**:
   ```
   liquidations_feed/adapters/your_exchange/
      __init__.py
      perpetual_adapter.py
      constants.py
   ```

2. **Implement required methods**:
   - `_get_ws_subscription_payload()` (WebSocket forceOrder stream)
   - `parse_ws_message()` (parse liquidation event)
   - `get_trading_pairs()` (supported trading pairs)

3. **Add comprehensive tests**:
   - Unit tests for all methods
   - Integration tests with mock WebSocket server
   - Error handling tests

4. **Update documentation**:
   - Add to supported exchanges list
   - Include usage examples
   - Document any special requirements

## Pull Request Guidelines

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes Made
- List specific changes
- Include any breaking changes
- Note documentation updates

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] No critical lint violations

## Security Review
- [ ] No secrets committed
- [ ] Dependencies reviewed
- [ ] Security scan passed
```

### Review Process

1. **Automated checks**: All CI checks must pass
2. **Code review**: At least one maintainer review required
3. **Security review**: Automatic security scanning
4. **Documentation**: Updates reviewed for accuracy

## Getting Help

### Resources

- **Issues**: Report bugs or request features
- **Discussions**: Ask questions or discuss ideas

### Contact

- **Security issues**: See SECURITY.md for reporting procedures
- **General questions**: Create a GitHub issue
- **Feature requests**: Create a GitHub issue with "enhancement" label

## Recognition

Contributors will be recognized in:
- Release notes for significant contributions
- Contributors list in repository
- Security advisories (for security researchers)

Thank you for contributing to hb-liquidations-feed!
