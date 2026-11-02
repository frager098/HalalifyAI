from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import pytest

from src.model_training.feature_ablation.feature_inventory import (
    EXPECTED_AVAILABILITY,
    build_feature_inventory_report,
    same_inventory_content,
    write_feature_inventory_report,
)


@pytest.fixture(scope="module")
def inventory_evidence():
    return build_feature_inventory_report()


def test_every_dataset_column_is_approved_or_excluded(inventory_evidence):
    report, inventory = inventory_evidence

    assert report["status"] == "verified"
    assert report["column_counts"] == {
        "dataset_columns": 56,
        "approved_market_candidates": 14,
        "eligible_fundamentals": 0,
        "excluded_columns": 42,
    }
    assert len(inventory) == 56
    assert inventory["column"].is_unique
    assert set(inventory["status"]) == {"approved_market_candidate", "excluded"}
    assert inventory.loc[
        inventory["status"].eq("excluded"), "exclusion_reason"
    ].str.len().gt(0).all()


def test_features_have_expected_groups_availability_and_no_future_inputs(
    inventory_evidence,
):
    report, inventory = inventory_evidence

    assert report["groups"] == {
        "momentum": ["momentum_5d", "momentum_20d", "momentum_60d"],
        "volatility": ["volatility_20d", "volatility_60d"],
        "downside_trend": [
            "return_1d",
            "downside_dev_20d",
            "drawdown_from_peak_60d",
            "price_to_sma20",
            "price_to_sma50",
        ],
        "market_relative": [
            "spy_momentum_20d",
            "excess_momentum_20d",
            "market_beta_60d",
        ],
        "volume": ["volume_ratio_20d"],
        "eligible_fundamentals": [],
    }
    approved = inventory.loc[
        inventory["status"].eq("approved_market_candidate")
    ].set_index("column")
    for feature, (first_date, missing_rows) in EXPECTED_AVAILABILITY.items():
        assert approved.loc[feature, "earliest_usable_date"] == first_date
        assert approved.loc[feature, "missing_rows"] == missing_rows
        assert "at or before t" in approved.loc[
            feature, "information_availability_rule"
        ]

    excluded = inventory.loc[inventory["status"].eq("excluded")].set_index("column")
    for column in (
        "target_window_end",
        "return_next_20d",
        "risk_volatility_next_20d",
        "relative_return_class",
        "risk_class",
    ):
        assert excluded.loc[column, "group"] in {"future_target", "target_label"}


def test_inventory_writer_refuses_existing_evidence(tmp_path):
    json_path = tmp_path / "feature_inventory.json"
    csv_path = tmp_path / "feature_inventory.csv"
    json_path.write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_feature_inventory_report(json_path, csv_path)

    assert json_path.read_text(encoding="utf-8") == "preserve"
    assert not csv_path.exists()


def test_inventory_content_allows_relocated_source_hash_but_not_changed_features():
    saved = {
        "groups": {"momentum": ["momentum_20d"]},
        "features": [{"column": "momentum_20d", "formula": "close ratio"}],
        "code_sha256": {"src/model_training/feature_inventory.py": "old-hash"},
    }
    current = {
        "groups": {"momentum": ["momentum_20d"]},
        "features": [{"column": "momentum_20d", "formula": "close ratio"}],
        "code_sha256": {
            "src/model_training/feature_ablation/feature_inventory.py": "new-hash"
        },
    }

    assert same_inventory_content(saved, current)
    current["features"][0]["formula"] = "changed formula"
    assert not same_inventory_content(saved, current)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
