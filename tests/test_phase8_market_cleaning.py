from pathlib import Path

import pandas as pd

from src.data_pipeline.clean_phase8_market_data import compare_overlap, load_config


def frame(adjusted_close: float = 9.5, close: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "session_date": "2025-10-01",
                "open": 9.0,
                "high": 11.0,
                "low": 8.0,
                "close": close,
                "volume": 100.0,
                "adjusted_close": adjusted_close,
            }
        ]
    )


def test_cleaning_config_is_separate_and_outcome_free():
    config = load_config(Path("configs/phase8_cleaning_v1.json"))
    assert config["output_directory"].startswith("data/processed/phase8_market_cleaned/")
    assert config["overlap_period"]["end"] < config["evaluation_period"]["start"]
    assert "model_inputs" not in config["output_directory"]


def test_adjusted_close_asof_drift_is_documented_but_structural_match_passes():
    rows, summary = compare_overlap(
        frame(adjusted_close=9.5),
        frame(adjusted_close=9.4),
        start="2025-10-01",
        end="2025-12-31",
        rtol=1e-12,
        atol=1e-10,
    )
    assert len(rows) == 1
    assert summary["accepted"] is True
    assert summary["structural_changed_cells"] == 0
    assert summary["adjusted_close_changed_rows"] == 1
    assert summary["classification"] == "all_adjusted_close_asof_drift_documented"


def test_structural_overlap_revision_fails_acceptance():
    _, summary = compare_overlap(
        frame(close=10.0),
        frame(close=10.5),
        start="2025-10-01",
        end="2025-12-31",
        rtol=1e-12,
        atol=1e-10,
    )
    assert summary["accepted"] is False
    assert summary["classification"] == "unexplained_structural_provider_revision"


def test_overlap_key_mismatch_fails_acceptance():
    current = frame()
    current["session_date"] = "2025-10-02"
    _, summary = compare_overlap(
        frame(),
        current,
        start="2025-10-01",
        end="2025-12-31",
        rtol=1e-12,
        atol=1e-10,
    )
    assert summary["accepted"] is False
    assert summary["classification"] == "overlap_key_mismatch"
