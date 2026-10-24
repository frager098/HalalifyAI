import unittest

import numpy as np
import pandas as pd

from src.legacy.model_experiments.run_walk_forward_evaluation import (
    classes,
    development_folds,
    estimator,
    rebalance_dates,
    thresholds,
)


class WalkForwardTests(unittest.TestCase):
    def test_shared_dates_and_actual_label_ends_are_purged(self):
        dates = pd.bdate_range("2023-01-02", periods=125).strftime("%Y-%m-%d").tolist()
        frame = pd.DataFrame([
            {"ticker": ticker, "session_date": date,
             "target_window_end": dates[i + 20] if i + 20 < len(dates) else None}
            for i, date in enumerate(dates) for ticker in ("AAA", "BBB")
        ])
        folds = list(development_folds(frame, "2024-01-01", n_splits=2, test_size=25))
        self.assertEqual(len(folds), 2)
        for _, train, evaluation, info in folds:
            self.assertEqual(info["gap_sessions"], 20)
            self.assertEqual(frame.loc[train, "target_window_end"].max() < info["evaluation_first_date"], True)
            self.assertEqual(frame.loc[evaluation, "target_window_end"].max() <= info["evaluation_last_feature_date"], True)
            self.assertTrue(frame.loc[train | evaluation].groupby("session_date").ticker.nunique().eq(2).all())

    def test_thresholds_come_only_from_supplied_training_values(self):
        cut = thresholds(np.arange(1, 301))
        self.assertEqual(classes([1, 150, 300], cut).tolist(), ["low", "medium", "high"])
        self.assertNotEqual(cut, thresholds(np.arange(1001, 1301)))

    def test_monthly_rank_dates_do_not_overlap_label_windows(self):
        rows = []
        for date, end in (("2024-01-02", "2024-02-02"), ("2024-02-01", "2024-03-01"),
                          ("2024-03-04", "2024-04-01")):
            for i in range(50):
                rows.append({"ticker": f"T{i:02d}", "session_date": date, "target_window_end": end})
        self.assertEqual(rebalance_dates(pd.DataFrame(rows)),
                         [("2024-01-02", "2024-02-02"), ("2024-03-04", "2024-04-01")])

    def test_ridge_preprocessing_is_fit_on_training_rows_only(self):
        model = estimator("ridge")
        training = pd.DataFrame({"factor": [1.0, 2.0, 3.0, np.nan]})
        model.fit(training, [1.0, 2.0, 3.0, 2.0])
        before = model.named_steps["standardscaler"].mean_.copy()
        model.predict(pd.DataFrame({"factor": [100000.0]}))
        np.testing.assert_array_equal(before, model.named_steps["standardscaler"].mean_)


if __name__ == "__main__":
    unittest.main()
