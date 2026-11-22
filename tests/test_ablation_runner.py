import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import pandas as pd
import pytest

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.model_training.feature_ablation.ablation_runner import (
    AblationContractError,
    _labels,
    build_experiment_plan,
    select_matched_features,
    tune_on_inner_validation,
    write_ablation_experiment,
)
import src.model_training.feature_ablation.ablation_runner as ablation_runner
from src.model_training.feature_ablation.feature_inventory import FEATURE_CATALOG


@pytest.fixture
def inventory_report():
    groups = {
        name: [feature for feature, item in FEATURE_CATALOG.items() if item["group"] == name]
        for name in (
            "momentum",
            "volatility",
            "downside_trend",
            "market_relative",
            "volume",
        )
    }
    groups["eligible_fundamentals"] = []
    return {"status": "verified", "groups": groups}


def _fold_rows(evaluation_date="2020-01-03", training_end="2020-01-02"):
    train = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "session_date": ["2020-01-01", "2020-01-01"],
            "target_window_end": [training_end, training_end],
            **{feature: [1.0, 2.0] for feature in FEATURE_COLUMNS},
        }
    )
    evaluation = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "session_date": [evaluation_date, evaluation_date],
            "target_window_end": ["2020-01-10", "2020-01-10"],
            **{feature: [3.0, 4.0] for feature in FEATURE_COLUMNS},
        }
    )
    return train, evaluation


def test_plan_has_single_cumulative_and_leave_one_group_out_comparisons(inventory_report):
    plan = build_experiment_plan(inventory_report)

    assert len(plan) == 14
    assert [row["name"] for row in plan[:5]] == [
        "single_momentum",
        "single_volatility",
        "single_downside_trend",
        "single_market_relative",
        "single_volume",
    ]
    assert [len(row["groups"]) for row in plan[5:9]] == [2, 3, 4, 5]
    assert [row["name"] for row in plan[9:]] == [
        "without_momentum",
        "without_volatility",
        "without_downside_trend",
        "without_market_relative",
        "without_volume",
    ]
    for experiment in plan[9:]:
        assert experiment["excluded_group"] not in experiment["groups"]
    assert set(feature for row in plan[:5] for feature in row["features"]) == set(
        FEATURE_COLUMNS
    )
    assert plan == build_experiment_plan(inventory_report)


def test_plan_rejects_fundamentals_and_unapproved_features(inventory_report):
    inventory_report["groups"]["eligible_fundamentals"] = ["debt_ratio"]
    with pytest.raises(AblationContractError, match="before the Step 6.10 gate"):
        build_experiment_plan(inventory_report)

    inventory_report["groups"]["eligible_fundamentals"] = []
    inventory_report["groups"]["momentum"].append("return_next_20d")
    with pytest.raises(AblationContractError, match="unapproved columns"):
        build_experiment_plan(inventory_report)


def test_feature_selection_keeps_rows_and_rejects_non_allowlisted_fields():
    train, evaluation = _fold_rows()
    x_train, x_evaluation = select_matched_features(
        train, evaluation, ["momentum_5d", "momentum_20d"]
    )

    assert list(x_train.columns) == ["momentum_5d", "momentum_20d"]
    assert list(x_evaluation.columns) == list(x_train.columns)
    assert len(x_train) == len(train)
    assert len(x_evaluation) == len(evaluation)

    with pytest.raises(AblationContractError, match="Non-allowlisted"):
        select_matched_features(train, evaluation, ["target_window_end"])


def test_feature_selection_rejects_overlapping_outcome_windows():
    train, evaluation = _fold_rows(training_end="2020-01-03")

    with pytest.raises(AblationContractError, match="outcome overlaps"):
        select_matched_features(train, evaluation, ["momentum_20d"])


def test_risk_labels_use_the_cutoff_for_the_requested_fold_role():
    train = pd.DataFrame({"risk_volatility_next_20d": [0.18, 0.25, 0.50]})
    evaluation = pd.DataFrame({"risk_volatility_next_20d": [0.15, 0.35, 0.55]})
    fold = {
        "tasks": {
            "risk": {
                "inner": {
                    "risk_boundaries": [0.20, 0.40],
                    "train_class_counts": [1, 1, 1],
                    "evaluation_class_counts": [1, 1, 1],
                },
                "outer": {
                    "risk_boundaries": [0.10, 0.30],
                    "train_class_counts": [0, 2, 1],
                    "evaluation_class_counts": [0, 1, 2],
                },
            }
        }
    }

    inner_train, inner_eval, inner_boundaries = _labels(
        train, evaluation, fold, "risk", role="inner"
    )
    outer_train, outer_eval, outer_boundaries = _labels(
        train, evaluation, fold, "risk", role="outer"
    )

    assert inner_boundaries == [0.20, 0.40]
    assert outer_boundaries == [0.10, 0.30]
    assert inner_train.tolist() == [0, 1, 2]
    assert outer_train.tolist() == [1, 1, 2]
    assert inner_eval.tolist() == [0, 1, 2]
    assert outer_eval.tolist() == [1, 2, 2]


def test_run_writer_refuses_existing_output_before_training(tmp_path):
    output = tmp_path / "existing_run"
    output.mkdir()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_ablation_experiment(
            "return", "LogisticRegression", "single_momentum", output
        )


def test_tuning_receives_only_inner_rows_and_uses_primary_metric(monkeypatch):
    fit_calls = []

    def fake_fit_predict(estimator, parameters, x_train, y_train, x_eval):
        fit_calls.append((len(x_train), len(y_train), len(x_eval)))
        if parameters["C"] == 1:
            prediction = [0, 0, 1, 1, 2, 2]
        else:
            prediction = [2, 2, 2, 2, 2, 2]
        probabilities = pd.get_dummies(pd.Series(prediction)).reindex(
            columns=[0, 1, 2], fill_value=0
        ).to_numpy(dtype=float)
        return probabilities

    monkeypatch.setattr(
        "src.model_training.feature_ablation.ablation_runner._fit_predict",
        fake_fit_predict,
    )
    x_train = pd.DataFrame({"momentum_20d": [1.0, 2.0, 3.0]})
    x_validation = pd.DataFrame({"momentum_20d": [4.0] * 6})
    validation_rows = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D", "E", "F"],
            "session_date": ["2020-02-03"] * 6,
            "return_next_20d": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
        }
    )

    selected, candidates = tune_on_inner_validation(
        "risk",
        "LogisticRegression",
        [{"C": 1}, {"C": 10}],
        x_train,
        pd.Series([0, 1, 2]).to_numpy(),
        x_validation,
        pd.Series([0, 0, 1, 1, 2, 2]).to_numpy(),
        validation_rows,
    )

    assert selected == {"C": 1}
    assert candidates[0]["primary_score"] > candidates[1]["primary_score"]
    assert fit_calls == [(3, 3, 6), (3, 3, 6)]


def test_recovery_validation_creates_a_no_fit_plan(monkeypatch, tmp_path, inventory_report):
    """The recovery route may validate a plan but must not train a model."""

    inventory = {
        **inventory_report,
        "evidence_mode": (
            "reconstructed_phase_3_and_4_inputs; "
            "original_phase_5_reports_unavailable"
        ),
        "input_identities": {
            "dataset": {"path": "recovery.csv", "sha256": "dataset-hash"},
            "metadata": {"path": "metadata.json", "sha256": "metadata-hash"},
            "chronological_protocol": {
                "path": "protocol.json",
                "sha256": "protocol-hash",
            },
        },
    }
    inventory_path = tmp_path / "feature_inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

    monkeypatch.setattr(
        ablation_runner,
        "build_recovery_feature_inventory_report",
        lambda *_: (inventory, pd.DataFrame()),
    )
    report = ablation_runner.build_recovery_runner_validation_report(
        tmp_path / "market_features_and_labels.csv",
        tmp_path / "dataset_metadata.json",
        tmp_path / "chronological_evaluation_protocol.json",
        inventory_path,
    )

    assert report["status"] == "validated"
    assert report["model_fitting_performed"] is False
    assert report["phase_5_comparison_recreated"] is False
    assert len(report["planned_experiments"]) == 14


def test_momentum_decision_requires_consistent_return_improvement():
    assert ablation_runner._momentum_decision(
        "return", 0.02, [0.01, 0.02, 0.03, -0.01]
    ) == "retain"
    assert ablation_runner._momentum_decision(
        "return", -0.01, [-0.02, 0.01, -0.01, 0.0]
    ) == "reject"
    assert ablation_runner._momentum_decision(
        "return", 0.01, [0.03, -0.02, -0.01, 0.04]
    ) == "inconclusive"


def test_momentum_risk_decision_respects_safety_guardrails():
    assert ablation_runner._momentum_decision(
        "risk",
        0.02,
        [0.01, 0.02, 0.03, -0.01],
        mean_high_recall_difference=0.01,
        high_to_low_difference=0,
    ) == "retain"
    assert ablation_runner._momentum_decision(
        "risk",
        0.02,
        [0.01, 0.02, 0.03, -0.01],
        mean_high_recall_difference=-0.01,
        high_to_low_difference=0,
    ) == "inconclusive"


def test_volatility_summary_rejects_consistently_worse_return_results():
    def run(experiment, scores):
        return {
            "task": "return",
            "estimator": "HistGradientBoosting",
            "experiment": {"name": experiment},
            "folds": [
                {
                    "fold": number,
                    "outer_training_rows": 10,
                    "outer_evaluation_rows": 5,
                    "outer_training_keys_sha256": f"train-{number}",
                    "outer_evaluation_keys_sha256": f"eval-{number}",
                    "outer_first": f"202{number}-01-01",
                    "outer_last": f"202{number}-02-01",
                    "metrics": {"mean_daily_spearman": score},
                }
                for number, score in enumerate(scores, start=1)
            ],
        }

    summary = ablation_runner.summarize_volatility_comparison(
        "return",
        run("full", [0.01, 0.00, 0.02, 0.01]),
        run("without_volatility", [0.02, 0.01, 0.03, 0.02]),
    )

    assert summary["decision"] == "reject"
    assert summary["positive_fold_count"] == 0
    assert summary["nonpositive_fold_count"] == 4


def test_downside_trend_summary_refuses_mismatched_coverage():
    template = {
        "task": "return",
        "estimator": "HistGradientBoosting",
        "folds": [
            {
                "fold": 1,
                "outer_training_rows": 10,
                "outer_evaluation_rows": 5,
                "outer_training_keys_sha256": "train",
                "outer_evaluation_keys_sha256": "eval",
                "outer_first": "2020-01-01",
                "outer_last": "2020-02-01",
                "metrics": {"mean_daily_spearman": 0.01},
            }
        ],
    }
    changed = {**template, "folds": [{**template["folds"][0], "outer_evaluation_rows": 4}]}

    with pytest.raises(AblationContractError, match="changed fold coverage"):
        ablation_runner.summarize_downside_trend_comparison(
            "return", template, changed
        )


def test_market_relative_summary_uses_the_shared_decision_rule():
    def run(scores):
        return {
            "task": "return",
            "estimator": "HistGradientBoosting",
            "folds": [
                {
                    "fold": number,
                    "outer_training_rows": 10,
                    "outer_evaluation_rows": 5,
                    "outer_training_keys_sha256": f"train-{number}",
                    "outer_evaluation_keys_sha256": f"eval-{number}",
                    "outer_first": f"202{number}-01-01",
                    "outer_last": f"202{number}-02-01",
                    "metrics": {"mean_daily_spearman": score},
                }
                for number, score in enumerate(scores, start=1)
            ],
        }

    summary = ablation_runner.summarize_market_relative_comparison(
        "return",
        run([0.03, 0.02, 0.04, 0.01]),
        run([0.02, 0.01, 0.03, 0.00]),
    )

    assert summary["decision"] == "retain"
    assert summary["positive_fold_count"] == 4


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

