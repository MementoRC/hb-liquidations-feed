"""Unit tests for liquidation data types."""

from dataclasses import fields

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide


class TestLiquidationSide:
    def test_liquidation_side_values(self):
        assert LiquidationSide.SHORT.value == "SHORT"
        assert LiquidationSide.LONG.value == "LONG"

    def test_liquidation_side_str(self):
        assert str(LiquidationSide.SHORT) == "SHORT"
        assert str(LiquidationSide.LONG) == "LONG"

    def test_liquidation_side_enum_members(self):
        members = list(LiquidationSide)
        assert len(members) == 2
        assert LiquidationSide.SHORT in members
        assert LiquidationSide.LONG in members


class TestLiquidation:
    def test_liquidation_creation(self):
        liq = Liquidation(
            timestamp=1_700_000_000.0,
            trading_pair="BTC-USDT",
            quantity=0.5,
            price=30_000.0,
            side=LiquidationSide.LONG,
        )
        assert liq.timestamp == 1_700_000_000.0
        assert liq.trading_pair == "BTC-USDT"
        assert liq.quantity == 0.5
        assert liq.price == 30_000.0
        assert liq.side is LiquidationSide.LONG

    def test_liquidation_fields(self):
        field_names = [f.name for f in fields(Liquidation)]
        assert "timestamp" in field_names
        assert "trading_pair" in field_names
        assert "quantity" in field_names
        assert "price" in field_names
        assert "side" in field_names
        assert len(field_names) == 5

    def test_liquidation_short_side(self):
        liq = Liquidation(
            timestamp=1_700_000_001.0,
            trading_pair="ETH-USDT",
            quantity=1.0,
            price=2_000.0,
            side=LiquidationSide.SHORT,
        )
        assert liq.side is LiquidationSide.SHORT

    def test_liquidation_is_dataclass(self):
        """Liquidation is a dataclass and supports vars()."""
        liq = Liquidation(
            timestamp=0.0,
            trading_pair="BTC-USDT",
            quantity=1.0,
            price=1.0,
            side=LiquidationSide.LONG,
        )
        d = vars(liq)
        assert set(d.keys()) == {"timestamp", "trading_pair", "quantity", "price", "side"}
