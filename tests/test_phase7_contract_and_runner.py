import json

import numpy as np
import pandas as pd
import pytest

from src.model_training.phase7.contract import (
    FREEZE_PATH,
    HANDOFF_PATH,
    Phase7ContractError,
)
from src.model_training.phase7.review import _review_rule
from src.model_training.phase7.runner import (
    _classification_metrics,
    _select_features,
    _summarize_variant,
)


def test_phase7_frozen_candidates_match_handoff_design():
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))

    assert freeze["status"] == "frozen_development_candidate"
    assert len(freeze["original_phase5_features"]) == 14
    assert len(freeze["tasks"]["return"]["candidate_features"]) == 17
    assert len(freeze["tasks"]["risk"]["candidate_features"]) == 7
    assert handoff["phase7_output_root"] == (
        "reports/model_evaluation/phase7_candidate_tuning_v1"
    )


def test_phase7_feature_selection_rejects_non_allowlisted_and_missing_values():
    train = pd.DataFrame({"allowed": [1.0, 2.0], "missing": [1.0, np.nan]})
    evaluation = pd.DataFrame({"allowed": [3.0], "missing": [2.0]})

    x_train, x_eval = _select_features(
        train, evaluation, ["allowed"], ["allowed", "missing"]
    )
    assert list(x_train) == list(x_eval) == ["allowed"]
    with pytest.raises(Phase7ContractError, match="non-allowlisted"):
        _select_features(train, evaluation, ["future_target"], ["allowed"])
    with pytest.raises(Phase7ContractError, match="missing"):
        _select_features(train, evaluation, ["missing"], ["allowed", "missing"])


def test_phase7_classification_metrics_include_probability_and_class_detail():
    truth = np.array([0, 1, 2, 2])
    probabilities = np.array(
        [[0.8, 0.1, 0.1], [0.1, 0.7, 0.2], [0.1, 0.2, 0.7], [0.6, 0.2, 0.2]]
    )
    result = _classification_metrics(truth, probabilities, ["Low", "Medium", "High"])

    assert set(result["per_class"]) == {"Low", "Medium", "High"}
    assert result["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [1, 0, 1]]
    assert result["log_loss"] > 0
    assert result["multiclass_brier"] > 0


def test_phase7_variant_summary_preserves_fold_consistency_and_risk_safety():
    folds = []
    for model, benchmark, recall, base_recall, severe, base_severe in (
        (0.60, 0.55, 0.70, 0.68, 2, 3),
        (0.61, 0.56, 0.71, 0.69, 1, 2),
        (0.59, 0.57, 0.66, 0.65, 2, 2),
        (0.58, 0.56, 0.67, 0.66, 1, 2),
    ):
        folds.append(
            {
                "metrics": {
                    "macro_f1": model,
                    "high_recall": recall,
                    "high_to_low_count": severe,
                },
                "benchmark": {
                    "macro_f1": benchmark,
                    "high_recall": base_recall,
                    "high_to_low_count": base_severe,
                },
            }
        )
    summary = _summarize_variant("risk", folds)

    assert summary["positive_fold_count_vs_benchmark"] == 4
    assert summary["mean_difference_vs_benchmark"] > 0
    assert summary["mean_high_recall_difference"] > 0
    assert summary["high_to_low_count_difference"] < 0


def test_phase7_review_rule_requires_consistency_and_risk_guardrails():
    return_summary = {
        "mean_difference_vs_benchmark": 0.01,
        "positive_fold_count_vs_benchmark": 3,
    }
    assert _review_rule("return", return_summary)[0] is True

    unsafe_risk = {
        **return_summary,
        "mean_high_recall_difference": -0.01,
        "high_to_low_count_difference": 0,
    }
    allowed, reasons = _review_rule("risk", unsafe_risk)
    assert allowed is False
    assert any("High-risk recall" in reason for reason in reasons)
