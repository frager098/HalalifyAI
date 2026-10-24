"""Point-in-time SEC feature invariants using small dated filings."""

import unittest

import pandas as pd

from src.data_pipeline.build_point_in_time_fundamentals import build_panel, resolve_fact_versions, extract_instant_facts


def row(field, end, filed, accession, value):
    return {"ticker": "AAA", "field": field, "concept": "Assets" if field == "assets_usd" else "CashAndCashEquivalentsAtCarryingValue",
            "period_end": end, "filing_date": filed,
            "available_date": (pd.Timestamp(filed) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "accession_number": accession, "value_usd": value}


class FundamentalPanelTests(unittest.TestCase):
    def test_extraction_rejects_duration_wrong_form_units_and_bad_accession(self):
        fact = dict(end='2024-03-31',filed='2024-05-01',val=100,accn='0000000001-24-000001',form='10-Q')
        payload = {'cik':1,'facts':{'us-gaap':{'Assets':{'units':{'USD':[
            fact, {**fact,'start':'2024-01-01'}, {**fact,'form':'10-Q/A'},
            {**fact,'val':-1}, {**fact,'end':'2024-06-30'}, {**fact,'accn':'bad'}],
            'EUR':[fact]}}}}}
        rows = extract_instant_facts(payload,'AAA','assets_usd','Assets')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['available_date'],'2024-05-02')
        self.assertEqual(rows[0]['source_observation'],1)
        self.assertEqual(rows[0]['cik'],'0000000001')

    def test_ratio_requires_same_filing_and_period(self):
        model = pd.DataFrame({'ticker':['AAA'],'session_date':['2024-05-03']})
        facts = pd.DataFrame([row('assets_usd','2024-03-31','2024-05-01','one',100),
                              row('cash_usd','2024-03-31','2024-05-01','two',20)])
        panel = build_panel(model,facts)
        self.assertTrue(panel.cash_to_assets.isna().all())
        self.assertFalse(panel.ratio_source_same_filing.any())

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
