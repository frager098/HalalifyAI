"""Regression checks for safe rejection, preservation, and loop convergence."""
import unittest
import pandas as pd
import numpy as np
from clean_data import price_pass, fact_pass, clean_loop, FACT_COLUMNS, calendar_sessions

class CleaningChecks(unittest.TestCase):
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
