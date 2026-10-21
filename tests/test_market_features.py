import unittest

import numpy as np
import pandas as pd

from src.features.market import FEATURE_COLUMNS, build_market_features


class MarketFeatureChecks(unittest.TestCase):
    def setUp(self):
        dates = pd.bdate_range("2020-01-01", periods=85).strftime("%Y-%m-%d")
        self.frame = pd.DataFrame({
            "ticker": ["AAA"] * len(dates),
            "session_date": dates,
            "adjusted_close": np.arange(100.0, 100.0 + len(dates)),
            "volume": [100.0] * len(dates),
            "spy_return": [np.nan] + [0.001] * (len(dates) - 1),
        })

    def test_current_and_future_rows_do_not_change_past_features(self):
        base = build_market_features(self.frame)
        changed = self.frame.copy()
        changed.loc[changed.index > 70, "adjusted_close"] *= 5
        changed.loc[changed.index > 70, "spy_return"] = -0.02
        revised = build_market_features(changed)
        pd.testing.assert_frame_equal(base.iloc[:71], revised.iloc[:71])
        self.assertEqual(list(base.columns), FEATURE_COLUMNS)
        self.assertAlmostEqual(base.loc[60, "momentum_20d"], 160 / 140 - 1)
        self.assertTrue(pd.isna(base.loc[59, "volatility_60d"]))

    def test_missing_bar_breaks_rolling_window(self):
        frame = self.frame.drop(index=60).reset_index(drop=True)
        frame = pd.concat([frame, self.frame.assign(ticker="BBB")], ignore_index=True)
        result = build_market_features(frame)
        aaa_at_61 = frame.index[(frame.ticker == "AAA") & (frame.session_date == self.frame.loc[61, "session_date"])][0]
        self.assertTrue(pd.isna(result.loc[aaa_at_61, "return_1d"]))
        self.assertTrue(pd.isna(result.loc[aaa_at_61, "volatility_20d"]))

    def test_duplicate_benchmark_disagreement_fails(self):
        frame = pd.concat([self.frame, self.frame.assign(ticker="BBB")], ignore_index=True)
        frame.loc[len(self.frame) + 5, "spy_return"] = 0.5
        with self.assertRaisesRegex(ValueError, "Conflicting SPY"):
            build_market_features(frame)


if __name__ == "__main__":
    unittest.main()
