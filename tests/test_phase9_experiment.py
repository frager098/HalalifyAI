"""Small checks for Phase 9 chronology and output protection."""

import pandas as pd
import pytest

from src.model_training.phase9_experiment import split_inner


def test_split_inner_purges_targets_before_calibration():
    dates = pd.date_range("2020-01-01", periods=106, freq="B")
    training = pd.DataFrame({"session_date": ["2019-12-01"],
                             "target_window_end": ["2019-12-20"]})
    validation = pd.DataFrame({"session_date": dates.strftime("%Y-%m-%d"),
                               "target_window_end": (dates + pd.offsets.BDay(20)).strftime("%Y-%m-%d")})
    _, tuning, calibration = split_inner(training, validation)
    assert tuning.target_window_end.max() < calibration.session_date.min()
    assert tuning.session_date.max() < calibration.session_date.min()


def test_split_inner_rejects_training_target_overlap():
    dates = pd.date_range("2020-01-01", periods=106, freq="B")
    training = pd.DataFrame({"session_date": ["2019-12-01"],
                             "target_window_end": ["2020-01-02"]})
    validation = pd.DataFrame({"session_date": dates.strftime("%Y-%m-%d"),
                               "target_window_end": (dates + pd.offsets.BDay(20)).strftime("%Y-%m-%d")})
    with pytest.raises(ValueError, match="overlaps tuning"):
        split_inner(training, validation)
