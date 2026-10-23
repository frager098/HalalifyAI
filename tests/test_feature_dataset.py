import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xc

from src.features.build_dataset import UNIVERSE, build_dataset, prepare_prices, sha256
from src.features.market import FEATURE_COLUMNS


class DatasetChecks(unittest.TestCase):
    def setUp(self):
        sessions = xc.get_calendar("XNYS").sessions_in_range("2020-01-02", "2020-05-29")
        self.frames = []
        for ticker in [*UNIVERSE, "SPY"]:
            price = 100 + np.arange(len(sessions), dtype=float)
            self.frames.append(pd.DataFrame(dict(ticker=ticker, session_date=sessions.strftime("%Y-%m-%d"),
                open=price, high=price+1, low=price-1, close=price, adjusted_close=price, volume=100)))
        self.frame = pd.concat(self.frames, ignore_index=True)

    def test_quorum_and_benchmark_alignment(self):
        for count in (44, 45, 49):
            selected = self.frame[self.frame.ticker.isin([*UNIVERSE[:count], "SPY"])].sample(frac=1, random_state=1)
            companies, _, _ = prepare_prices(selected)
            self.assertTrue(companies.active_peer_count.eq(count).all())
            self.assertTrue(companies.activity_quorum_met.eq(count >= 45).all())
            self.assertEqual(companies.session_date.tolist(), selected.loc[selected.ticker.ne("SPY"), "session_date"].tolist())
            first = companies.session_date.min()
            self.assertTrue(companies.loc[companies.session_date.eq(first), "spy_return"].isna().all())

    def test_input_rejections(self):
        cases = [pd.concat([self.frame, self.frame.iloc[:1]]), self.frame.drop(columns="volume"),
                 self.frame[self.frame.ticker.ne("SPY")], self.frame.assign(adjusted_close=np.inf),
                 self.frame.assign(session_date="not-a-date"), self.frame.assign(close=-1)]
        for frame in cases:
            with self.subTest(), self.assertRaises((ValueError, TypeError)):
                prepare_prices(frame)

    def test_saved_build_alignment_future_invariance_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prices.csv"
            frame = self.frame[self.frame.ticker.isin(["AAPL", "SPY"])].copy()
            frame.to_csv(source, index=False)
            first, metadata = build_dataset(source, root / "first", sha256(source))
            self.assertEqual(first.name, "market_features.csv")
            saved = pd.read_csv(first)
            self.assertEqual(saved.ticker.unique().tolist(), ["AAPL"])
            self.assertAlmostEqual(saved.loc[60, "momentum_20d"], 160/140-1)
            self.assertTrue(pd.isna(saved.loc[59, "volatility_60d"]))
            self.assertFalse(metadata["ready_for_training"])
            with self.assertRaises(FileExistsError):
                build_dataset(source, root / "first", sha256(source))
            with self.assertRaisesRegex(ValueError, "checksum"):
                build_dataset(source, root / "wrong", "bad")
            cutoff = saved.loc[70, "session_date"]
            future = frame.session_date.gt(cutoff)
            frame.loc[future, ["open", "high", "low", "close", "adjusted_close"]] *= 2
            frame.to_csv(source, index=False)
            revised, _ = build_dataset(source, root / "second", sha256(source))
            pd.testing.assert_frame_equal(saved.loc[:70, FEATURE_COLUMNS], pd.read_csv(revised).loc[:70, FEATURE_COLUMNS])


if __name__ == "__main__":
    unittest.main()
