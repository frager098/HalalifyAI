"""Reusable Phase 7 model-comparison runner for the frozen candidates."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    recall_score,
)

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.baseline_models import _return_ranking, fold_roles
from src.model_training.chronological_evaluation_protocol import (
    _hash_keys,
    apply_risk_boundaries,
)
from src.model_training.feature_ablation.ablation_runner import (
    _fit_predict,
    _labels,
    _parameters,
)
from src.model_training.phase7.contract import (
    DATASET_PATH,
    EXPERIMENT_CONTRACT,
    FREEZE_PATH,
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    RUNNER_VALIDATION,
    VARIANT_ORDER,
    Phase7ContractError,
    _read_json,
    load_verified_inputs,
)


ESTIMATOR_SLUGS = {
    "LogisticRegression": "logistic_regression",
    "HistGradientBoosting": "hist_gradient_boosting",
}


def _probability_metrics(truth: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    observed = np.eye(3)[truth]
    return {
        "log_loss": float(log_loss(truth, probabilities, labels=[0, 1, 2])),
        "multiclass_brier": float(
            np.mean(np.sum((probabilities - observed) ** 2, axis=1))
        ),
    }


def _classification_metrics(
    truth: np.ndarray, probabilities: np.ndarray, class_names: list[str]
) -> dict[str, Any]:
    prediction = probabilities.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, prediction, labels=[0, 1, 2], zero_division=0
    )
    return {
        "macro_f1": float(f1_score(truth, prediction, labels=[0, 1, 2], average="macro", zero_division=0)),
        "ordinal_mae": float(np.mean(np.abs(truth - prediction))),
        "confusion_matrix": confusion_matrix(truth, prediction, labels=[0, 1, 2]).tolist(),
        "per_class": {
            name: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, name in enumerate(class_names)
        },
        **_probability_metrics(truth, probabilities),
    }


def _select_features(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    columns: list[str],
    allowlist: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not columns or len(columns) != len(set(columns)):
        raise Phase7ContractError("Feature list is empty or duplicated")
    if set(columns) - set(allowlist):
        raise Phase7ContractError("A Phase 7 model requested a non-allowlisted feature")
    x_train, x_evaluation = train[columns].copy(), evaluation[columns].copy()
    if x_train.isna().any().any() or x_evaluation.isna().any().any():
        raise Phase7ContractError("Phase 7 model input contains a missing value")
    return x_train, x_evaluation


def _primary_score(
    task: str,
    rows: pd.DataFrame,
    truth: np.ndarray,
    probabilities: np.ndarray,
) -> float:
    if task == "return":
        ranking = _return_ranking(rows, probabilities[:, 2] - probabilities[:, 0])
        if ranking["mean_daily_spearman"] is None:
            raise Phase7ContractError("Return fold has no defined ranking dates")
        return float(ranking["mean_daily_spearman"])
    return float(
        f1_score(
            truth,
            probabilities.argmax(axis=1),
            labels=[0, 1, 2],
            average="macro",
            zero_division=0,
        )
    )


def _tune(
    task: str,
    estimator: str,
    grid: list[dict[str, Any]],
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    y_train: np.ndarray,
    y_evaluation: np.ndarray,
    features: list[str],
    allowlist: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    x_train, x_evaluation = _select_features(
        train, evaluation, features, allowlist
    )
    candidates = []
    for parameters in grid:
        probabilities = _fit_predict(
            estimator, parameters, x_train, y_train, x_evaluation
        )
        candidates.append(
            {
                "parameters": parameters,
                "primary_score": _primary_score(
                    task, evaluation, y_evaluation, probabilities
                ),
            }
        )
    # max() preserves the first declared setting on an exact tie.
    selected = max(candidates, key=lambda row: row["primary_score"])["parameters"]
    return selected, candidates


def _fold_metrics(
    task: str,
    evaluation: pd.DataFrame,
    truth: np.ndarray,
    probabilities: np.ndarray,
    risk_boundaries: list[float] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    names = ["Lower", "Middle", "Higher"] if task == "return" else ["Low", "Medium", "High"]
    metrics = _classification_metrics(truth, probabilities, names)
    if task == "return":
        ranking = _return_ranking(
            evaluation, probabilities[:, 2] - probabilities[:, 0]
        )
        benchmark = _return_ranking(evaluation, evaluation["momentum_20d"])
        metrics.update(
            mean_daily_spearman=ranking["mean_daily_spearman"],
            mean_top10_minus_universe=ranking["mean_top10_minus_universe"],
            defined_ranking_dates=ranking["defined_spearman_dates"],
        )
        benchmark_metrics = {
            "name": "momentum_20d",
            "mean_daily_spearman": benchmark["mean_daily_spearman"],
            "mean_top10_minus_universe": benchmark["mean_top10_minus_universe"],
            "defined_ranking_dates": benchmark["defined_spearman_dates"],
        }
    else:
        prediction = probabilities.argmax(axis=1)
        trailing = apply_risk_boundaries(
            evaluation["volatility_20d"], risk_boundaries
        )
        metrics.update(
            high_recall=float(
                recall_score(truth, prediction, labels=[2], average="macro", zero_division=0)
            ),
            high_to_low_count=int(((truth == 2) & (prediction == 0)).sum()),
            high_outcomes=int((truth == 2).sum()),
        )
        benchmark_metrics = {
            "name": "volatility_20d_with_fold_training_cutoffs",
            "macro_f1": float(
                f1_score(truth, trailing, labels=[0, 1, 2], average="macro", zero_division=0)
            ),
            "ordinal_mae": float(np.mean(np.abs(truth - trailing))),
            "confusion_matrix": confusion_matrix(truth, trailing, labels=[0, 1, 2]).tolist(),
            "high_recall": float(
                recall_score(truth, trailing, labels=[2], average="macro", zero_division=0)
            ),
            "high_to_low_count": int(((truth == 2) & (trailing == 0)).sum()),
        }
    return metrics, benchmark_metrics


def _prediction_rows(
    task: str,
    fold_number: int,
    variant: str,
    evaluation: pd.DataFrame,
    truth: np.ndarray,
    probabilities: np.ndarray,
    risk_boundaries: list[float] | None,
) -> pd.DataFrame:
    if task == "return":
        rows = evaluation[
            ["ticker", "session_date", "target_window_end", "return_next_20d", "momentum_20d"]
        ].copy()
        rows["fold_class"] = truth
        rows["p_lower"], rows["p_middle"], rows["p_higher"] = probabilities.T
        rows["rank_score"] = probabilities[:, 2] - probabilities[:, 0]
        rows["benchmark_score"] = evaluation["momentum_20d"].to_numpy()
    else:
        rows = evaluation[
            ["ticker", "session_date", "target_window_end", "risk_volatility_next_20d", "volatility_20d"]
        ].copy()
        rows["fold_class"] = truth
        rows["p_low"], rows["p_medium"], rows["p_high"] = probabilities.T
        rows["benchmark_predicted_class"] = apply_risk_boundaries(
            evaluation["volatility_20d"], risk_boundaries
        )
    rows.insert(0, "variant", variant)
    rows.insert(0, "fold", fold_number)
    rows["predicted_class"] = probabilities.argmax(axis=1)
    return rows


def _summarize_variant(task: str, folds: list[dict[str, Any]]) -> dict[str, Any]:
    primary = "mean_daily_spearman" if task == "return" else "macro_f1"
    benchmark_primary = primary
    values = [row["metrics"][primary] for row in folds]
    benchmark = [row["benchmark"][benchmark_primary] for row in folds]
    summary: dict[str, Any] = {
        "primary_metric": primary,
        "fold_values": values,
        "mean_primary": float(np.mean(values)),
        "benchmark_fold_values": benchmark,
        "benchmark_mean_primary": float(np.mean(benchmark)),
        "fold_differences_vs_benchmark": [
            float(value - base) for value, base in zip(values, benchmark)
        ],
    }
    differences = summary["fold_differences_vs_benchmark"]
    summary["mean_difference_vs_benchmark"] = float(np.mean(differences))
    summary["positive_fold_count_vs_benchmark"] = int(
        sum(value > 0 for value in differences)
    )
    if task == "risk":
        high_recall = [row["metrics"]["high_recall"] for row in folds]
        benchmark_recall = [row["benchmark"]["high_recall"] for row in folds]
        summary.update(
            mean_high_recall=float(np.mean(high_recall)),
            benchmark_mean_high_recall=float(np.mean(benchmark_recall)),
            mean_high_recall_difference=float(
                np.mean(np.asarray(high_recall) - np.asarray(benchmark_recall))
            ),
            high_to_low_count=int(
                sum(row["metrics"]["high_to_low_count"] for row in folds)
            ),
            benchmark_high_to_low_count=int(
                sum(row["benchmark"]["high_to_low_count"] for row in folds)
            ),
        )
        summary["high_to_low_count_difference"] = (
            summary["high_to_low_count"] - summary["benchmark_high_to_low_count"]
        )
    return summary


def run_model_comparison(
    task: str,
    estimator: str,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Tune comparator and candidate inside each fold, then score outer rows once."""

    if task not in {"return", "risk"}:
        raise ValueError("Task must be 'return' or 'risk'")
    if estimator not in ESTIMATOR_SLUGS:
        raise ValueError("Unsupported Phase 7 estimator")
    for prerequisite in (EXPERIMENT_CONTRACT, RUNNER_VALIDATION):
        if not prerequisite.is_file():
            raise FileNotFoundError(f"Run Phase 7 Steps 7.1-7.3 first: {prerequisite}")
    contract = _read_json(EXPERIMENT_CONTRACT, "Phase 7 experiment contract")
    validation = _read_json(RUNNER_VALIDATION, "Phase 7 runner validation")
    if contract.get("status") != "frozen_before_model_results" or validation.get("status") != "validated":
        raise Phase7ContractError("Phase 7 preparation is incomplete")

    frame, _, protocol, freeze, _ = load_verified_inputs()
    output_dir = Path(output_dir or (OUTPUT_ROOT / task / ESTIMATOR_SLUGS[estimator]))
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 7 model evidence: {output_dir}")
    variants = {
        "comparator": freeze["original_phase5_features"],
        "candidate": freeze["tasks"][task]["candidate_features"],
    }
    grid = _parameters(protocol, estimator)
    allowlist = protocol["feature_allowlist"]
    reports: dict[str, list[dict[str, Any]]] = {name: [] for name in VARIANT_ORDER}
    prediction_parts: dict[str, list[pd.DataFrame]] = {name: [] for name in VARIANT_ORDER}

    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, task, "inner")
        outer_train, outer_eval = fold_roles(frame, fold, task, "outer")
        y_inner_train, y_inner_eval, _ = _labels(
            inner_train, inner_eval, fold, task, role="inner"
        )
        y_outer_train, y_outer_eval, boundaries = _labels(
            outer_train, outer_eval, fold, task, role="outer"
        )
        for variant in VARIANT_ORDER:
            features = variants[variant]
            selected, candidates = _tune(
                task,
                estimator,
                grid,
                inner_train,
                inner_eval,
                y_inner_train,
                y_inner_eval,
                features,
                allowlist,
            )
            x_train, x_eval = _select_features(
                outer_train, outer_eval, features, allowlist
            )
            probabilities = _fit_predict(
                estimator, selected, x_train, y_outer_train, x_eval
            )
            metrics, benchmark = _fold_metrics(
                task, outer_eval, y_outer_eval, probabilities, boundaries
            )
            reports[variant].append(
                {
                    "fold": fold["fold"],
                    "features": features,
                    "selected_parameters": selected,
                    "inner_candidates": candidates,
                    "inner_training_rows": len(inner_train),
                    "inner_evaluation_rows": len(inner_eval),
                    "outer_training_rows": len(outer_train),
                    "outer_evaluation_rows": len(outer_eval),
                    "inner_training_keys_sha256": _hash_keys(inner_train),
                    "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
                    "outer_training_keys_sha256": _hash_keys(outer_train),
                    "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
                    "risk_boundaries": boundaries,
                    "metrics": metrics,
                    "benchmark": benchmark,
                }
            )
            prediction_parts[variant].append(
                _prediction_rows(
                    task,
                    fold["fold"],
                    variant,
                    outer_eval,
                    y_outer_eval,
                    probabilities,
                    boundaries,
                )
            )

    for fold_index in range(4):
        left = reports["comparator"][fold_index]
        right = reports["candidate"][fold_index]
        if (
            left["outer_evaluation_keys_sha256"]
            != right["outer_evaluation_keys_sha256"]
            or left["outer_evaluation_rows"] != right["outer_evaluation_rows"]
        ):
            raise Phase7ContractError("Comparator and candidate evaluation rows differ")

    output_dir.mkdir(parents=True, exist_ok=False)
    summaries = {}
    for variant in VARIANT_ORDER:
        predictions = pd.concat(prediction_parts[variant], ignore_index=True)
        prediction_path = output_dir / f"{variant}_outer_predictions.csv"
        predictions.to_csv(
            prediction_path, index=False, lineterminator="\n", float_format="%.17g"
        )
        summary = _summarize_variant(task, reports[variant])
        report = {
            "schema_version": 1,
            "stage": f"phase_7_{task}_{ESTIMATOR_SLUGS[estimator]}",
            "status": "complete",
            "task": task,
            "estimator": estimator,
            "variant": variant,
            "features": variants[variant],
            "dataset_sha256": sha256(DATASET_PATH),
            "protocol_sha256": sha256(PROTOCOL_PATH),
            "freeze_sha256": sha256(FREEZE_PATH),
            "experiment_contract_sha256": sha256(EXPERIMENT_CONTRACT),
            "code_sha256": sha256(__file__),
            "environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "parameter_grid": grid,
            "selection_rule": contract["tuning_rule"],
            "folds": reports[variant],
            "summary": summary,
            "prediction_rows": len(predictions),
            "prediction_sha256": sha256(prediction_path),
        }
        (output_dir / f"{variant}_report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        summaries[variant] = summary

    primary = "mean_daily_spearman" if task == "return" else "macro_f1"
    paired_fold_differences = [
        float(
            reports["candidate"][index]["metrics"][primary]
            - reports["comparator"][index]["metrics"][primary]
        )
        for index in range(4)
    ]
    paired = {
        "schema_version": 1,
        "stage": f"phase_7_{task}_{ESTIMATOR_SLUGS[estimator]}_paired_summary",
        "status": "complete",
        "task": task,
        "estimator": estimator,
        "primary_metric": primary,
        "comparator": summaries["comparator"],
        "candidate": summaries["candidate"],
        "candidate_minus_comparator_by_fold": paired_fold_differences,
        "candidate_minus_comparator_mean": float(np.mean(paired_fold_differences)),
        "candidate_positive_fold_count": int(
            sum(value > 0 for value in paired_fold_differences)
        ),
        "matched_rows": True,
        "limitations": freeze["limitations"],
    }
    (output_dir / "paired_summary.json").write_text(
        json.dumps(paired, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return paired
