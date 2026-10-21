"""The core keeps float epoch seconds; hb_compat exposes upstream's int-ms view."""

import pandas as pd

from liquidations_feed.core.liquidation_data import Liquidation, LiquidationSide
from liquidations_feed.hb_compat.common import liquidations_df_with_ms, seconds_to_ms


class TestSecondsToMs:
    def test_returns_int(self):
        assert isinstance(seconds_to_ms(1_700_000_000.123), int)

    def test_float_error_does_not_truncate(self):
        # 1700000000.123 * 1000 == 1700000000122.9999... in binary floating point
        assert seconds_to_ms(1_700_000_000.123) == 1_700_000_000_123


class TestLiquidationsDfWithMs:
    def _df(self):
        liq = Liquidation(1_700_000_000.123, "BTC-USDT", 0.5, 30_000.0, LiquidationSide.LONG)
        return pd.DataFrame([liq.__dict__])

    def test_timestamp_column_is_int_ms(self):
        out = liquidations_df_with_ms(self._df())
        assert out["timestamp"].iloc[0] == 1_700_000_000_123
        assert pd.api.types.is_integer_dtype(out["timestamp"])

    def test_other_columns_and_input_unchanged(self):
        df = self._df()
        out = liquidations_df_with_ms(df)
        assert list(out.columns) == list(df.columns)
        assert df["timestamp"].iloc[0] == 1_700_000_000.123
        assert out["price"].iloc[0] == 30_000.0

    def test_empty_frame_keeps_columns(self):
        empty = pd.DataFrame(columns=["timestamp", "trading_pair", "quantity", "price", "side"])
        out = liquidations_df_with_ms(empty)
        assert list(out.columns) == list(empty.columns)
        assert out.empty
