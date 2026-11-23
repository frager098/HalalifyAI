import json
from pathlib import Path

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.phase6_expansion_features import (
    EXPANSION_FEATURE_COLUMNS,
    EXPANSION_GROUPS,
)
from src.model_training.feature_ablation.phase5_continuation import (
    OUTPUT_ROOT as CONTINUATION_OUTPUT_ROOT,
)
from src.model_training.feature_ablation.phase6_market_expansion import (
    DATASET as EXPANDED_DATASET,
    OUTPUT_ROOT as EXPANSION_OUTPUT_ROOT,
)
from src.target_engineering.build_phase6_expanded_dataset import DEFAULT_SOURCE


CONFIG = Path("configs/phase6_market_feature_expansion_v1.json")


def test_precommitment_freezes_exactly_six_features_in_two_disjoint_groups():
    contract = json.loads(CONFIG.read_text(encoding="utf-8"))
    configured = {
        feature
        for group in contract["groups"].values()
        for feature in group["features"]
    }

    assert contract["status"] == "prepared_for_student_execution"
    assert configured == set(EXPANSION_FEATURE_COLUMNS)
    assert len(configured) == 6
    assert set(EXPANSION_GROUPS) == set(contract["groups"])
    assert not set(FEATURE_COLUMNS) & configured
    assert contract["comparison"]["folds"] == 4
    assert contract["new_dataset"]["overwrite_parent"] is False


def test_precommitment_records_formula_availability_and_risk_safety():
    contract = json.loads(CONFIG.read_text(encoding="utf-8"))

    for group in contract["groups"].values():
        assert group["availability"]
        assert all(formula for formula in group["features"].values())
    assert "High-risk recall" in contract["decision_rule"]["retain"]
    assert "High-predicted-Low" in contract["decision_rule"]["retain"]
    assert contract["comparison"]["rows"].startswith("Identical")


def test_expansion_paths_cannot_overwrite_parent_or_continuation_evidence():
    assert EXPANDED_DATASET != DEFAULT_SOURCE
    assert EXPANSION_OUTPUT_ROOT != CONTINUATION_OUTPUT_ROOT
    assert CONTINUATION_OUTPUT_ROOT not in EXPANSION_OUTPUT_ROOT.parents
