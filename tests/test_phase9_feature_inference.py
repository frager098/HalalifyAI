"""Point-in-time reconstruction and rejection tests for Phase 9.6."""

import numpy as np
import pandas as pd
import pytest

from src.model_training.phase9_feature_inference import reconstruct_phase9_features


@pytest.fixture(scope="module")
def historical_panel():
    frame = pd.read_csv(
        "data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv",
        low_memory=False,
    )
    date = "2024-05-30"
    sessions = sorted(frame.loc[frame.session_date.le(date), "session_date"].unique())[-61:]
    bars = frame.loc[frame.session_date.isin(sessions),
                     ["ticker", "session_date", "adjusted_close", "volume", "spy_return"]]
    return frame, bars.sort_values(["session_date", "ticker"]).reset_index(drop=True), date


def test_reconstruction_matches_frozen_rows(historical_panel):
    frozen, bars, date = historical_panel
    roster = set(frozen.loc[frozen.session_date.eq(date), "ticker"])
    result = reconstruct_phase9_features(bars, date, roster)
    expected = frozen.loc[frozen.session_date.eq(date), result.columns].sort_values("ticker").reset_index(drop=True)
    assert len(result) == 50
    assert result[["ticker", "session_date"]].equals(expected[["ticker", "session_date"]])
    feature_names = result.columns.drop(["ticker", "session_date"])
    np.testing.assert_allclose(result[feature_names], expected[feature_names], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("date", ["2016-03-31", "2021-06-25"])
def test_an_earlier_historical_date_matches_frozen_rows(historical_panel, date):
    frozen, _, _ = historical_panel
    sessions = sorted(frozen.loc[frozen.session_date.le(date), "session_date"].unique())[-61:]
    bars = frozen.loc[frozen.session_date.isin(sessions),
                      ["ticker", "session_date", "adjusted_close", "volume", "spy_return"]]
    bars = bars.sort_values(["session_date", "ticker"]).reset_index(drop=True)
    roster = set(frozen.loc[frozen.session_date.eq(date), "ticker"])
    result = reconstruct_phase9_features(bars, date, roster)
    expected = frozen.loc[frozen.session_date.eq(date), result.columns].sort_values("ticker").reset_index(drop=True)
    assert result[["ticker", "session_date"]].equals(expected[["ticker", "session_date"]])
    features = result.columns.drop(["ticker", "session_date"])
    np.testing.assert_allclose(result[features], expected[features], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("change,match", [
    ("duplicate", "Duplicate"),
    ("unknown", "Unknown"),
    ("nonfinite", "Nonfinite"),
    ("missing_session", "Missing exchange sessions"),
    ("missing_peer", "Incomplete decision-date ticker roster"),
    ("extra_column", "Expected exactly"),
])
def test_rejects_invalid_panels(historical_panel, change, match):
    _, original, date = historical_panel
    bars = original.copy()
    if change == "duplicate":
        bars = pd.concat([bars, bars.iloc[[-1]]], ignore_index=True)
    elif change == "unknown":
        bars.loc[bars.index[-1], "ticker"] = "UNKNOWN"
    elif change == "nonfinite":
        bars.loc[bars.index[-1], "adjusted_close"] = np.inf
    elif change == "missing_session":
        bars = bars.loc[bars.session_date.ne(sorted(bars.session_date.unique())[10])]
    elif change == "missing_peer":
        keep = set(sorted(bars.ticker.unique())[:44])
        bars = bars.loc[bars.ticker.isin(keep)]
    else:
        bars["future_return"] = 0.0
    with pytest.raises(ValueError, match=match):
        reconstruct_phase9_features(bars, date, set(original.loc[original.session_date.eq(date), "ticker"]))


def test_rejects_stale_date_and_short_history(historical_panel):
    _, bars, date = historical_panel
    with pytest.raises(ValueError, match="Bars must end"):
        reconstruct_phase9_features(bars, "2024-05-31", set(bars.loc[bars.session_date.eq(date), "ticker"]))
    short = bars.loc[bars.session_date.isin(sorted(bars.session_date.unique())[-60:])]
    with pytest.raises(ValueError, match="insufficient rolling history"):
        reconstruct_phase9_features(short, date, set(bars.loc[bars.session_date.eq(date), "ticker"]))
