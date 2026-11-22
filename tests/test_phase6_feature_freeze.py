"""Guard the versioned Phase 6 feature-freeze setting."""

import json
from pathlib import Path

from src.model_training.feature_ablation.feature_inventory import FEATURE_CATALOG


FREEZE_PATH = Path("configs/phase6_feature_freeze_v1.json")


def test_phase6_freeze_uses_only_allowlisted_market_features():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    allowed = set(FEATURE_CATALOG)

    assert freeze["status"] == "frozen_development_candidate"
    assert freeze["fundamental_features"] == []
    assert freeze["fundamental_gate"] == "blocked_by_phase_6_10"
    assert freeze["protocol"]["reused_test_period_used_for_selection"] is False

    for task in ("return", "risk"):
        features = freeze["tasks"][task]["candidate_features"]
        assert len(features) == len(set(features))
        assert set(features) <= allowed
        assert freeze["tasks"][task]["combined_candidate_was_not_refit_in_phase_6"] is True

    assert set(freeze["tasks"]["return"]["candidate_features"]) == {
        "volume_ratio_20d",
        "spy_momentum_20d",
        "excess_momentum_20d",
        "market_beta_60d",
    }
    assert "market_relative" in freeze["tasks"]["risk"]["rejected_groups"]
