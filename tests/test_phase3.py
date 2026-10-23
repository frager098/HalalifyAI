import unittest
import numpy as np
import pandas as pd
from src.labels.phase3 import outcomes, relative_classes, risk_classes, model_inputs
from src.features.market import FEATURE_COLUMNS


class Phase3Checks(unittest.TestCase):
    def test_outcome_window_and_gap(self):
        import exchange_calendars as xc
        dates = xc.get_calendar('XNYS').sessions_in_range('2020-01-02','2020-05-29').strftime('%Y-%m-%d')
        close = 100*np.cumprod(1+np.sin(np.arange(len(dates)))*0.01)
        frame = pd.DataFrame(dict(ticker='AAPL', session_date=dates, adjusted_close=close))
        result = outcomes(frame)
        self.assertAlmostEqual(result.return_next_20d.iloc[0], close[20]/close[0]-1)
        self.assertAlmostEqual(result.risk_volatility_next_20d.iloc[0], np.std(close[1:21]/close[:20]-1,ddof=1)*np.sqrt(252))
        self.assertTrue(result.return_next_20d.tail(20).isna().all())
        self.assertTrue(pd.isna(outcomes(frame.drop(index=10)).return_next_20d.iloc[0]))

    def test_peer_quorum_and_ties(self):
        for n in [44,45,49,50]:
            frame = pd.DataFrame(dict(volume=np.ones(n),return_next_20d=np.ones(n),session_date='2020-01-02',active_peer_count=n))
            out = relative_classes(frame)
            if n<45:
                self.assertTrue(out.relative_return_class.isna().all())
            else:
                self.assertTrue(out.relative_return_class.eq(1).all())
            frame.loc[0,'return_next_20d'] = np.nan
            if n==45:
                self.assertTrue(relative_classes(frame).relative_return_class.isna().all())

    def test_training_boundaries_purge_and_allowlist(self):
        frame = pd.DataFrame({c: np.ones(100) for c in FEATURE_COLUMNS})
        frame['nominal_split'] = ['train']*60+['validation']*40
        frame['target_window_end'] = ['2022-12-01']*59+['2022-12-28']+['2023-01-01']*40
        frame['risk_volatility_next_20d'] = np.linspace(.1,.8,100)
        frame['relative_return_class'] = 1
        result, boundaries = risk_classes(frame)
        frame.loc[60:,'risk_volatility_next_20d'] *= 100
        revised, later = risk_classes(frame)
        self.assertEqual(boundaries,later)
        self.assertEqual(result.dataset_split.iloc[59],'purged')
        self.assertFalse(result.risk_eligible.iloc[59])
        with self.assertRaises(ValueError):
            model_inputs(result,['risk_class'])
        pd.testing.assert_series_equal(result.risk_class.iloc[:60],revised.risk_class.iloc[:60])
