import pandas as pd
import unittest

from src.data.reconcile_price_history import next_session_table, price_events


class PriceReconciliationTests(unittest.TestCase):
    def test_completed_daily_bar_starts_at_next_observed_session(self):
        table = next_session_table(["2024-01-08", "2024-01-05", "2024-01-05"])
        self.assertEqual(table.feature_session.tolist(), ["2024-01-05", "2024-01-08"])
        self.assertEqual(table.first_usable_session_for_execution.iloc[0], "2024-01-08")
        self.assertTrue(pd.isna(table.first_usable_session_for_execution.iloc[1]))
        with self.assertRaisesRegex(ValueError, "No reference sessions"):
            next_session_table([])


    def test_large_move_and_adjustment_difference_are_separate_reviews(self):
        rows = pd.DataFrame([
            {"ticker": "AMD", "session_date": "2016-04-22", "split_close_return": .52,
             "provider_all_adjusted_return": .5201, "large_return_review": True},
            {"ticker": "GE", "session_date": "2023-01-04", "split_close_return": -.17,
             "provider_all_adjusted_return": .06, "large_return_review": False},
        ])
        events = price_events(rows)
        self.assertEqual(events.review_kind.tolist(), ["large_move", "adjustment_difference"])
        self.assertTrue(events.loc[1, "documented_event"].startswith("GE HealthCare"))
        self.assertFalse(events.price_independently_verified.any())


if __name__ == "__main__":
    unittest.main()
