import pandas as pd
import unittest

from src.data_pipeline.reconcile_market_price_history import next_session_table, price_events
from src.data_pipeline.audit_market_price_sources import compare_raw_pages
from pathlib import Path
import tempfile
import json
import hashlib


class PriceReconciliationTests(unittest.TestCase):
    def test_raw_comparison_detects_changes_and_missing_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = []
            for basis in ('split','all'):
                path = root/f'{basis}_0001.json'
                path.write_text(json.dumps({'bars':{'AAA':[{'t':'2024-01-02T05:00:00Z',
                    'o':10,'h':12,'l':9,'c':11,'v':100}]}}))
                pages.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            interim = pd.DataFrame([dict(ticker='AAA',session_date='2024-01-02',open=10,high=12,low=9,close=10,volume=100,adjusted_close=11),
                                    dict(ticker='BBB',session_date='2024-01-02',open=10,high=12,low=9,close=11,volume=100,adjusted_close=11)])
            summary, changes = compare_raw_pages(root, {'pages':pages}, interim)
            self.assertEqual(summary.differing_values_or_keys.sum(), 1)
            self.assertEqual(len(changes[changes.reason.eq('interim_only')]), 2)
            self.assertEqual(changes.loc[changes.reason.eq('value_difference'),'column'].tolist(), ['close'])

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
