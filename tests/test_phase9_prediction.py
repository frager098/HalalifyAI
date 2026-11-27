"""End-to-end package inference checks; these do not score future outcomes."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.model_training.phase9_prediction import predict_phase9


@pytest.fixture(scope="module")
def frozen_dataset():
    return pd.read_csv(
        "data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv",
        usecols=["ticker", "session_date", "adjusted_close", "volume", "spy_return"],
    )


def panel(frame, date):
    sessions = sorted(frame.loc[frame.session_date.le(date), "session_date"].unique())[-61:]
    bars = frame.loc[frame.session_date.isin(sessions)].sort_values(["session_date", "ticker"]).reset_index(drop=True)
    roster = set(frame.loc[frame.session_date.eq(date), "ticker"])
    return bars, roster


@pytest.mark.parametrize("date,count", [("2016-03-31", 49), ("2021-06-25", 50), ("2024-05-30", 50)])
def test_prediction_contract_and_determinism(frozen_dataset, date, count):
    bars, roster = panel(frozen_dataset, date)
    first = predict_phase9(bars, date, roster)
    second = predict_phase9(bars, date, roster)
    assert first == second
    assert first["session_date"] == date
    assert first["decision_time"] == "after_close"
    assert first["horizon_trading_sessions"] == 20
    assert first["evidence_status"] == "development_only"
    assert first["return_model_version"] == "phase9_return_v1"
    assert first["risk_model_version"] == "phase9_risk_v1"
    assert len(first["predictions"]) == count
    assert {row["ticker"] for row in first["predictions"]} == roster
    assert [row["return_rank"] for row in first["predictions"]] == list(range(1, count + 1))
    assert first["predictions"] == sorted(first["predictions"], key=lambda row: (-row["return_rank_score"], row["ticker"]))
    for row in first["predictions"]:
        assert row["return_class"] in ["Lower", "Middle", "Higher"]
        assert row["risk_class"] in ["Low", "Medium", "High"]
        assert list(row["return_probabilities"]) == ["Lower", "Middle", "Higher"]
        assert list(row["risk_probabilities"]) == ["Low", "Medium", "High"]
        assert np.isclose(sum(row["return_probabilities"].values()), 1)
        assert np.isclose(sum(row["risk_probabilities"].values()), 1)
        assert np.isclose(row["return_rank_score"], row["return_probabilities"]["Higher"] - row["return_probabilities"]["Lower"])
        assert "expected_return" not in row and "shariah_status" not in row


def test_packaged_aapl_fixture_matches_complete_inference(frozen_dataset):
    date = "2024-05-30"
    bars, roster = panel(frozen_dataset, date)
    output = predict_phase9(bars, date, roster)
    aapl = next(row for row in output["predictions"] if row["ticker"] == "AAPL")
    for task in ("return", "risk"):
        expected = json.loads((Path(f"reports/model_evaluation/phase9_{task}_package_v1") / "fixture_expected.json").read_text())
        actual = list(aapl[f"{task}_probabilities"].values())
        np.testing.assert_allclose(actual, expected["probabilities"], rtol=0, atol=1e-12)


def test_invalid_panel_and_package_fail_closed(frozen_dataset):
    date = "2024-05-30"
    bars, roster = panel(frozen_dataset, date)
    with pytest.raises(ValueError, match="Incomplete decision-date ticker roster"):
        predict_phase9(bars.loc[bars.ticker.ne("AAPL")], date, roster)
    with pytest.raises(ValueError, match="Bars must end"):
        predict_phase9(bars, "2024-05-31", roster)
    wrong_package = Path("reports/model_evaluation/nonexistent_phase9_return_package_fixture")
    assert not wrong_package.exists()
    with pytest.raises(FileNotFoundError):
        predict_phase9(bars, date, roster, return_package=wrong_package)
