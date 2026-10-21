"""Point-in-time SEC feature invariants using small dated filings."""

import unittest

import pandas as pd

from src.data.build_pit_fundamentals import build_panel, resolve_fact_versions


def row(field, end, filed, accession, value):
    return {"ticker": "AAA", "field": field, "concept": "Assets" if field == "assets_usd" else "CashAndCashEquivalentsAtCarryingValue",
            "period_end": end, "filing_date": filed,
            "available_date": (pd.Timestamp(filed) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "accession_number": accession, "value_usd": value}


class FundamentalPanelTests(unittest.TestCase):
    def test_future_filing_is_unavailable_and_old_amendment_does_not_replace_new_period(self):
        model = pd.DataFrame({"ticker": ["AAA"] * 4,
                              "session_date": ["2024-04-15", "2024-04-17", "2024-05-03", "2024-06-03"]})
        facts = pd.DataFrame([
            row("assets_usd", "2024-03-31", "2024-04-16", "q1", 100),
            row("cash_usd", "2024-03-31", "2024-04-16", "q1", 20),
            row("assets_usd", "2023-12-31", "2024-04-16", "q1", 75),
            row("assets_usd", "2024-04-30", "2024-05-02", "q2", 120),
            row("cash_usd", "2024-04-30", "2024-05-02", "q2", 30),
            row("assets_usd", "2024-03-31", "2024-06-01", "amend_q1", 105),
        ])
        selected, conflicts = resolve_fact_versions(facts)
        self.assertTrue(conflicts.empty)
        panel = build_panel(model, selected)
        self.assertTrue(pd.isna(panel.assets_usd.iloc[0]))
        self.assertEqual(panel.assets_usd.iloc[1], 100)
        self.assertEqual(panel.assets_period_end.iloc[1], "2024-03-31")
        self.assertEqual(panel.cash_to_assets.iloc[1], .2)
        self.assertEqual(panel.assets_usd.iloc[2], 120)
        self.assertEqual(panel.assets_usd.iloc[3], 120)

    def test_conflicting_same_filing_fact_is_quarantined(self):
        facts = pd.DataFrame([
            row("assets_usd", "2024-03-31", "2024-04-16", "q1", 100),
            row("assets_usd", "2024-03-31", "2024-04-16", "q1", 101),
        ])
        selected, conflicts = resolve_fact_versions(facts)
        self.assertTrue(selected.empty)
        self.assertEqual(len(conflicts), 2)


if __name__ == "__main__":
    unittest.main()
