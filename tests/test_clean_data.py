"""Regression checks for safe rejection, preservation, and loop convergence."""
import unittest
import pandas as pd
import numpy as np
from src.data.clean_data import price_pass, fact_pass, clean_loop, FACT_COLUMNS, calendar_sessions, recover_json_bytes, verify_inputs
from src.data.validate_data import restore_price_snapshot
import hashlib
import json
from pathlib import Path
import tempfile

class CleaningChecks(unittest.TestCase):
    def test_recovery_requires_exact_original_hash_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'original'
            source.mkdir()
            raw = b'{"bars":{"AAA":[{"c":1.25}]}}'
            pretty = json.dumps(json.loads(raw), indent=2).encode()
            page = source/'split_0001.json'
            page.write_bytes(pretty)
            expected = hashlib.sha256(raw).hexdigest()
            recovered, method = recover_json_bytes(page, expected)
            self.assertEqual(recovered, raw)
            self.assertIn('matches_original_digest', method)
            metadata = {'dataset_version':'original','pages':[{'file':page.name,'sha256':expected}]}
            (source/'metadata.json').write_text(json.dumps(metadata))
            destination = Path(folder)/'restored'
            restored = restore_price_snapshot(source, metadata, destination)
            self.assertEqual(page.read_bytes(), pretty)
            self.assertEqual((destination/page.name).read_bytes(), raw)
            self.assertEqual(restored['pages'], metadata['pages'])
            page.write_text('{"bars":{"AAA":[{"c":2.25}]}}')
            with self.assertRaisesRegex(ValueError, 'Cannot reconstruct'):
                recover_json_bytes(page, expected)

    def test_market_only_verification_does_not_bypass_price_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            csv = root/'prices.csv'
            csv.write_bytes(b'known')
            (root/'metadata.json').write_text('{}')
            page = root/'split_0001.json'
            page.write_bytes(b'{}')
            metadata = {'normalized_sha256':hashlib.sha256(b'known').hexdigest(),
                        'pages':[{'file':page.name,'sha256':hashlib.sha256(b'{}').hexdigest()}]}
            verify_inputs(root, None, metadata, {}, csv, market_only=True)
            page.write_bytes(b'{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify_inputs(root, None, metadata, {}, csv, market_only=True)

    def price(self, **overrides):
        d = dict(ticker=' aapl ',session_date='2025-01-02',open=10,high=12,low=9,close=11,volume=100,adjusted_close=10.5,source_row=2)
        d.update(overrides)
        return d

    def test_price_conflicts_duplicates_and_invalid_rows(self):
        df=pd.DataFrame([self.price(),self.price(source_row=3),self.price(close=10,source_row=4),
                         self.price(ticker='MSFT',high=8),self.price(ticker='NVDA',volume=np.inf),
                         self.price(ticker='AMD',session_date='01/02/2025'), self.price(ticker='SPY')])
        h=[]
        good,bad=clean_loop(df,lambda d:price_pass(d,'2025-01-01','2025-01-31'),'prices',h,6)
        self.assertEqual(good.ticker.tolist(),['SPY'])
        self.assertEqual(len(bad),6)
        self.assertTrue(h[-1]['stable'])
        self.assertTrue(bad.rejection_reason.str.contains('conflicting_ticker_date').any())

    def test_sec_preserves_units_amendments_and_negative_values(self):
        base=dict(ticker='AAPL',cik='0000320193',entity_name='Apple',taxonomy='us-gaap',concept='NetIncomeLoss',label='Net income',unit='USD',start='2024-01-01',end='2024-12-31',val=-100,accn='original',fy=2024,fp='FY',form='10-K',filed='2025-02-01',frame=None,source_file='fixture',source_row=1)
        rows=[base,{**base,'source_row':2},{**base,'accn':'amendment','filed':'2025-03-01','val':-90,'source_row':3},
              {**base,'unit':'EUR','val':-80,'source_row':4},
              {**base,'concept':'Assets','val':100,'source_row':5},{**base,'concept':'Assets','val':110,'source_row':6},
              {**base,'concept':'Other','start':'2025-01-01','source_row':7}]
        h=[]
        good,bad=clean_loop(pd.DataFrame(rows,columns=FACT_COLUMNS),fact_pass,'facts',h,6)
        self.assertEqual(len(good),3)
        self.assertTrue(good.val.lt(0).all())
        self.assertEqual(len(bad),4)
        self.assertTrue(h[-1]['stable'])
        self.assertEqual(good.accn.nunique(),2)

    def test_calendar_holiday_and_extraordinary_closure(self):
        dates,basis=calendar_sessions('2016-01-01','2025-12-31',pd.DataFrame(),False)
        self.assertNotIn(pd.Timestamp('2016-01-01'),dates)
        self.assertNotIn(pd.Timestamp('2025-01-09'),dates)
        self.assertIn(pd.Timestamp('2025-01-02'),dates)
        self.assertTrue(basis.startswith('XNYS'))

    def test_forward_disclosure_is_not_deleted_as_bad_data(self):
        row = dict(ticker='AMD',cik='0000002488',taxonomy='us-gaap',concept='ExpectedCost',
                   unit='USD',start=None,end='2026-12-31',val=100,accn='original',filed='2025-02-01')
        frame=pd.DataFrame([row]).reindex(columns=FACT_COLUMNS)
        good,bad=fact_pass(frame)
        self.assertEqual(len(good),1)
        self.assertTrue(bad.empty)

    def test_nonconvergence_fails(self):
        def flip(df):
            return pd.DataFrame({'x':1-df.x}),pd.DataFrame()
        with self.assertRaises(RuntimeError):
            clean_loop(pd.DataFrame({'x':[0]}),flip,'flip',[],2)

if __name__=='__main__':
    unittest.main()
