import unittest

import pandas as pd

from src.modeling.monthly_rank_validation import choose_rebalance_dates


class MonthlyRankDateChecks(unittest.TestCase):
    def test_skips_partial_month_and_overlapping_target_windows(self):
        dates_and_ends = [
            ("2022-12-28", "2023-01-26"),
            ("2023-01-03", "2023-01-31"),
            ("2023-02-01", "2023-03-02"),
            ("2023-03-01", "2023-03-29"),
            ("2023-04-03", "2023-05-01"),
        ]
        frame = pd.DataFrame([
            {"ticker": f"T{i:02d}", "session_date": date, "target_window_end": end}
            for date, end in dates_and_ends for i in range(50)
        ])
        self.assertEqual(
            choose_rebalance_dates(frame),
            [("2023-01-03", "2023-01-31"),
             ("2023-02-01", "2023-03-02"),
             ("2023-04-03", "2023-05-01")],
        )


if __name__ == "__main__":
    unittest.main()
