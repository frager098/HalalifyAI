"""Guards for the student-run final development fit."""

import pandas as pd
import pytest

from src.model_training.phase9_final_fit import _labels, _select, run_final_fit


def test_risk_boundaries_use_training_rows_only():
    train = pd.DataFrame({"risk_volatility_next_20d": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    validation = pd.DataFrame({"risk_volatility_next_20d": [100.0, 200.0]})
    y_train, y_validation, boundaries = _labels("risk", train, validation)
    assert boundaries == train.risk_volatility_next_20d.quantile([1 / 3, 2 / 3]).tolist()
    assert y_train.tolist() == [0, 0, 1, 1, 2, 2]
    assert y_validation.tolist() == [2, 2]


def test_selection_refuses_target_overlap_before_fitting():
    train = pd.DataFrame({"target_window_end": ["2023-01-03"]})
    validation = pd.DataFrame({"session_date": ["2023-01-03"]})
    with pytest.raises(ValueError, match="overlaps validation"):
        _select("return", train, validation, ["return_1d"], {})


def test_final_fit_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "phase9_final_fit_v1"
    output.mkdir()
    with pytest.raises(FileExistsError, match="Preserve existing"):
        run_final_fit(tmp_path / "unused.json", output)
