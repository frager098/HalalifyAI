import json
from pathlib import Path

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.phase6_expansion_features import (
    CROSS_SECTIONAL_FEATURES,
    EXPANSION_FEATURE_COLUMNS,
)


FREEZE_PATH = Path("configs/phase6_feature_freeze_v2.json")


def test_v2_freeze_uses_the_exact_tested_return_augmentation():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    candidate = freeze["tasks"]["return"]["candidate_features"]

    assert freeze["status"] == "frozen_development_candidate"
    assert candidate == FEATURE_COLUMNS + CROSS_SECTIONAL_FEATURES
    assert freeze["tasks"]["return"]["candidate_was_directly_evaluated_in_phase_6"] is True
    assert freeze["tasks"]["return"]["positive_fold_count"] == 3
    assert freeze["expansion_decisions"]["market_regime"]["return"] == "inconclusive"


def test_v2_freeze_risk_candidate_contains_only_retained_continuation_groups():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    risk = freeze["tasks"]["risk"]

    assert set(risk["candidate_features"]) == {
        "volatility_20d",
        "volatility_60d",
        "return_1d",
        "downside_dev_20d",
        "drawdown_from_peak_60d",
        "price_to_sma20",
        "price_to_sma50",
    }
    assert risk["retained_continuation_groups"] == ["volatility", "downside_trend"]
    assert risk["combined_candidate_was_not_refit_in_phase_6"] is True
    assert freeze["expansion_decisions"]["cross_sectional_relative_strength"]["risk"] == "reject"


def test_v2_freeze_does_not_promote_fundamentals_or_inconclusive_expansion_features():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    candidates = {
        feature
        for task in freeze["tasks"].values()
        for feature in task["candidate_features"]
    }

    assert freeze["fundamental_features"] == []
    assert freeze["fundamental_gate"] == "blocked_by_phase_6_10"
    assert not (set(EXPANSION_FEATURE_COLUMNS) - set(CROSS_SECTIONAL_FEATURES)) & candidates
    assert freeze["protocol"]["reused_test_period_used_for_selection"] is False
