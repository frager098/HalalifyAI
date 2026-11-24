import numpy as np
import pandas as pd

from src.model_training.phase8.build_reserved_dataset import (
    add_forward_outcomes,
    apply_frozen_labels,
)
from src.feature_engineering.market_features import FEATURE_COLUMNS


def test_forward_outcomes_use_exactly_twenty_later_sessions():
    sessions = pd.bdate_range("2026-01-02", periods=25)
    frame = pd.DataFrame(
        {
            "ticker": "AAA",
            "session_date": sessions.strftime("%Y-%m-%d"),
            "adjusted_close": np.arange(100.0, 125.0),
        }
    )
    result = add_forward_outcomes(frame, sessions)
    assert result.loc[0, "target_window_end"] == sessions[20].strftime("%Y-%m-%d")
    assert result.loc[0, "return_next_20d"] == 120 / 100 - 1
    expected_risk = pd.Series(np.arange(100.0, 121.0)).pct_change().std(ddof=1) * np.sqrt(252)
    assert result.loc[0, "risk_volatility_next_20d"] == expected_risk
    assert result.loc[5:, "target_window_end"].isna().all()


def test_frozen_labels_use_peer_ranks_and_training_risk_cutoffs():
    rows = []
    for number in range(45):
        row = {
            "ticker": f"T{number:02d}",
            "session_date": "2026-01-02",
            "volume": 100,
            "active_peer_count": 45,
            "return_next_20d": float(number),
            "risk_volatility_next_20d": [0.10, 0.20, 0.40][number % 3],
        }
        row.update({feature: 1.0 for feature in FEATURE_COLUMNS})
        rows.append(row)
    result = apply_frozen_labels(pd.DataFrame(rows), 0.15, 0.30)
    assert result["return_eligible"].all()
    assert result["risk_eligible"].all()
    assert result["relative_return_class"].value_counts().sort_index().tolist() == [15, 15, 15]
    assert result["risk_class"].value_counts().sort_index().tolist() == [15, 15, 15]


def test_no_benchmark_score_or_performance_column_is_created():
    row = {
        "ticker": "AAA",
        "session_date": "2026-01-02",
        "volume": 100,
        "active_peer_count": 1,
        "return_next_20d": np.nan,
        "risk_volatility_next_20d": np.nan,
    }
    row.update({feature: 1.0 for feature in FEATURE_COLUMNS})
    result = apply_frozen_labels(pd.DataFrame([row]), 0.15, 0.30)
    forbidden = {"benchmark_score", "predicted_class", "macro_f1", "spearman"}
    assert forbidden.isdisjoint(result.columns)
