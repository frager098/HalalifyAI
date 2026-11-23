import json

import numpy as np
import pandas as pd
import pytest

from src.feature_engineering.build_feature_dataset import sha256
from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.phase6_expansion_features import EXPANSION_FEATURE_COLUMNS
import src.target_engineering.build_phase6_expanded_dataset as builder


def _source_frame(sessions=70, tickers=50):
    dates = pd.date_range("2020-01-02", periods=sessions, freq="B")
    rows = []
    for day, date in enumerate(dates):
        for ticker_number in range(tickers):
            row = {
                "ticker": f"T{ticker_number:02d}",
                "session_date": date.strftime("%Y-%m-%d"),
                "volume": 1000 + ticker_number,
                "active_peer_count": tickers,
                "activity_quorum_met": True,
                "spy_return": np.nan if day == 0 else 0.001 + day / 1_000_000,
                "return_eligible": day >= 60,
                "risk_eligible": day >= 60,
            }
            for offset, feature in enumerate(FEATURE_COLUMNS):
                row[feature] = ticker_number / 100 + day / 10_000 + offset / 1000
            rows.append(row)
    return pd.DataFrame(rows)


def test_builder_creates_new_version_and_preserves_every_parent_value(tmp_path, monkeypatch):
    source_dir = tmp_path / "parent"
    source_dir.mkdir()
    source = source_dir / "market_features_and_labels.csv"
    original = _source_frame()
    original.to_csv(source, index=False)
    metadata_path = source_dir / "dataset_metadata.json"
    metadata_path.write_text(
        json.dumps({"rows": len(original), "feature_columns": FEATURE_COLUMNS}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "EXPECTED_SOURCE_SHA256", sha256(source))
    monkeypatch.setattr(builder, "EXPECTED_METADATA_SHA256", sha256(metadata_path))
    output = tmp_path / "expanded"

    metadata = builder.build_expanded_dataset(source, output)
    expanded = pd.read_csv(output / "market_features_and_labels.csv", low_memory=False)

    pd.testing.assert_frame_equal(
        pd.read_csv(source, low_memory=False), expanded[original.columns]
    )
    assert metadata["dataset_version"] == "phase6_expanded_features_v1"
    assert metadata["added_feature_columns"] == EXPANSION_FEATURE_COLUMNS
    assert expanded.loc[expanded["return_eligible"], EXPANSION_FEATURE_COLUMNS].notna().all().all()
    assert source.is_file()
    with pytest.raises(FileExistsError):
        builder.build_expanded_dataset(source, output)


def test_builder_rejects_missing_new_features_on_an_eligible_row(tmp_path, monkeypatch):
    source_dir = tmp_path / "parent"
    source_dir.mkdir()
    source = source_dir / "market_features_and_labels.csv"
    original = _source_frame(tickers=44)
    original.to_csv(source, index=False)
    metadata_path = source_dir / "dataset_metadata.json"
    metadata_path.write_text(
        json.dumps({"rows": len(original), "feature_columns": FEATURE_COLUMNS}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "EXPECTED_SOURCE_SHA256", sha256(source))
    monkeypatch.setattr(builder, "EXPECTED_METADATA_SHA256", sha256(metadata_path))

    with pytest.raises(ValueError, match="eligible-row coverage"):
        builder.build_expanded_dataset(source, tmp_path / "expanded")

