import pandas as pd
import pytest

from src.evaluation.audited_training_review import validate_partitions, baseline_predictions
from src.features.core import FEATURES


def sample():
    frame = pd.DataFrame({
        'ticker': ['A', 'A', 'A'], 'split': ['train', 'validation', 'test'],
        'as_of_date': ['2018-01-02', '2020-01-02', '2023-01-03'],
        'label_end_date': ['2018-02-01', '2020-02-01', '2023-02-01'],
        'return_class': ['low', 'medium', 'high'], 'risk_class': ['high', 'low', 'medium']})
    for feature in FEATURES:
        frame[feature] = 1.0
    return frame


def test_blocks_target_crossing_boundary():
    frame = sample()
    frame.loc[0, 'label_end_date'] = '2020-01-02'
    with pytest.raises(ValueError, match='boundary'):
        validate_partitions(frame)


def test_blocks_duplicate_company_dates():
    frame = sample()
    with pytest.raises(ValueError, match='Duplicate'):
        validate_partitions(pd.concat([frame, frame.iloc[[0]]]))


def test_baseline_uses_training_majority_not_test_majority():
    frame = sample()
    parts = validate_partitions(frame)
    predictions = baseline_predictions(parts['train'], parts['test'], 'return_class',
        'ret_20d', {'lower_cutoff': 0.0, 'upper_cutoff': 0.5})
    assert predictions['training_majority'].tolist() == ['low']
    assert predictions['previous_20_sessions'].tolist() == ['high']
