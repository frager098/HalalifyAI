import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.market import FEATURE_COLUMNS
from src.modeling.evaluation_protocol import (assert_fold, apply_risk_boundaries,
    fit_training_pipeline, guarded_training_features, guarded_calibration_groups, load_and_audit)
from src.features.build_dataset import sha256


class RecordingEstimator:
    def fit(self, x, y):
        self.rows_seen = len(x)
        self.dates_seen = set(x.index)
        return self


class EvaluationProtocolChecks(unittest.TestCase):
    def test_saved_input_audit_and_corruption(self):
        source = Path('data/modeling/market_features_and_labels_phase3_v1/market_features_and_labels.csv')
        frame, metadata = load_and_audit(source)
        self.assertEqual(len(frame), 124987)
        self.assertEqual(metadata['eligible_counts']['risk'], 118987)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'market_features_and_labels.csv').write_bytes(source.read_bytes() + b'\n')
            (root/'dataset_metadata.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_and_audit(root/'market_features_and_labels.csv')

    def test_actual_end_purge_and_training_only_fit(self):
        frame = pd.DataFrame({c: [1., 2., 3.] for c in FEATURE_COLUMNS})
        frame['ticker'] = ['AAA']*3
        frame['session_date'] = ['2020-01-01','2020-01-02','2020-01-04']
        frame['target_window_end'] = ['2020-01-03','2020-01-05','2020-01-25']
        frame['return_next_20d'] = [.1,.2,.3]
        train, evaluation = frame.iloc[:1], frame.iloc[2:]
        assert_fold(train, evaluation, '2020-01-04')
        fitted, x_eval = fit_training_pipeline(RecordingEstimator(), train, evaluation, 'return_next_20d')
        self.assertEqual(fitted.rows_seen, 1)
        self.assertEqual(len(x_eval), 1)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            assert_fold(frame.iloc[:2], evaluation, '2020-01-04')
        with self.assertRaisesRegex(ValueError, 'Non-allowlisted'):
            guarded_training_features(train, evaluation, ['target_window_end'])
        later = frame.copy()
        later['session_date'] = ['2020-01-01', '2020-01-10', '2020-02-10']
        later['target_window_end'] = ['2020-01-05', '2020-01-15', '2020-02-20']
        fit, calibration = guarded_calibration_groups(later.iloc[:1], later.iloc[1:2], later.iloc[2:])
        self.assertEqual(len(fit), 1)
        self.assertEqual(len(calibration), 1)
        with self.assertRaisesRegex(ValueError, 'chronological'):
            guarded_calibration_groups(later.iloc[:1], later.iloc[2:], later.iloc[1:2])

    def test_fixed_risk_boundaries(self):
        values = pd.Series([0.1, 0.2, 0.3])
        self.assertEqual(apply_risk_boundaries(values, [0.1, 0.2]).tolist(), [0,1,2])
        with self.assertRaisesRegex(ValueError, 'Missing'):
            apply_risk_boundaries(pd.Series([np.nan]), [0.1,0.2])


if __name__ == '__main__':
    unittest.main()
