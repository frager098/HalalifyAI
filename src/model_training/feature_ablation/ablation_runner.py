"""Phase 6 controlled feature ablations on frozen Phase 4 folds.

The runner evaluates one predeclared experiment at a time. It tunes only on
that fold's inner training/validation rows, refits on outer training rows, and
scores the outer fold once. Notebook code should call these functions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.feature_engineering.build_feature_dataset import sha256
from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.model_training.baseline_models import (
    DEFAULT_DATA,
    DEFAULT_PROTOCOL,
    FROZEN_DATA_SHA256,
    FROZEN_PROTOCOL_SHA256,
    _return_ranking,
    fold_roles,
    verify_inputs,
)
from src.model_training.chronological_evaluation_protocol import (
    _hash_keys,
    apply_risk_boundaries,
    assert_fold,
)
from src.model_training.feature_ablation.ablation_contract import (
    DEFAULT_OUTPUT as DEFAULT_CONTRACT,
    build_ablation_contract_report,
)
from src.model_training.feature_ablation.feature_inventory import (
    DEFAULT_INVENTORY_JSON,
    build_feature_inventory_report,
    same_inventory_content,
)


DEFAULT_RUN_PLAN = Path(
    "reports/model_evaluation/feature_ablation/v1/runner_validation.json"
)
DEFAULT_GROUP_ORDER = (
    "momentum",
    "volatility",
    "downside_trend",
    "market_relative",
    "volume",
)


class AblationContractError(ValueError):
    """Raised when an experiment violates frozen inputs or comparison rules."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise AblationContractError(f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AblationContractError(f"Cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise AblationContractError(f"{label} must contain a JSON object")
    return value


def build_experiment_plan(inventory_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Create single-group, cumulative, and leave-one-group-out comparisons."""

    if inventory_report.get("status") != "verified":
        raise AblationContractError("A verified Step 6.2 inventory is required")
    groups = inventory_report.get("groups")
    expected_group_names = {*DEFAULT_GROUP_ORDER, "eligible_fundamentals"}
    if not isinstance(groups, dict) or set(groups) != expected_group_names or tuple(
        name for name in DEFAULT_GROUP_ORDER if name in groups
    ) != DEFAULT_GROUP_ORDER:
        raise AblationContractError("Step 6.2 market-group definitions differ")
    if groups.get("eligible_fundamentals") != []:
        raise AblationContractError(
            "Fundamentals cannot enter the runner before the Step 6.10 gate"
        )

    allowlist = set(FEATURE_COLUMNS)
    group_features: dict[str, list[str]] = {}
    for name in DEFAULT_GROUP_ORDER:
        columns = groups[name]
        if not columns or len(columns) != len(set(columns)):
            raise AblationContractError(f"Feature group {name!r} is empty or duplicated")
        if set(columns) - allowlist:
            raise AblationContractError(f"Feature group {name!r} contains unapproved columns")
        group_features[name] = list(columns)
    all_columns = [column for name in DEFAULT_GROUP_ORDER for column in group_features[name]]
    if len(all_columns) != len(set(all_columns)):
        raise AblationContractError("A feature appears in more than one group")
    if set(all_columns) != allowlist:
        raise AblationContractError("The market groups do not cover the full feature allowlist")

    plan = [
        {"name": f"single_{name}", "groups": [name], "features": group_features[name]}
        for name in DEFAULT_GROUP_ORDER
    ]
    cumulative_groups: list[str] = []
    cumulative_features: list[str] = []
    for name in DEFAULT_GROUP_ORDER:
        cumulative_groups.append(name)
        cumulative_features.extend(group_features[name])
        if len(cumulative_groups) > 1:
            plan.append(
                {
                    "name": "cumulative_" + "_plus_".join(cumulative_groups),
                    "groups": list(cumulative_groups),
                    "features": list(cumulative_features),
                }
            )
    for excluded_group in DEFAULT_GROUP_ORDER:
        included_groups = [
            name for name in DEFAULT_GROUP_ORDER if name != excluded_group
        ]
        included_features = [
            feature for name in included_groups for feature in group_features[name]
        ]
        plan.append(
            {
                "name": f"without_{excluded_group}",
                "groups": included_groups,
                "excluded_group": excluded_group,
                "features": included_features,
            }
        )
    return plan


def select_matched_features(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    columns: list[str],
    allowlist: list[str] = FEATURE_COLUMNS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select approved columns after checking chronology and complete values."""

    if not columns or len(columns) != len(set(columns)):
        raise AblationContractError("Feature selection is empty or contains duplicates")
    if set(allowlist) - set(FEATURE_COLUMNS):
        raise AblationContractError("Feature allowlist cannot extend the frozen Phase 3 allowlist")
    forbidden = set(columns) - set(allowlist)
    if forbidden:
        raise AblationContractError(f"Non-allowlisted features requested: {sorted(forbidden)}")
    if train.empty or evaluation.empty:
        raise AblationContractError("Training and evaluation rows must both be present")
    if train.duplicated(["ticker", "session_date"]).any() or evaluation.duplicated(
        ["ticker", "session_date"]
    ).any():
        raise AblationContractError("Duplicate ticker/session_date keys")
    try:
        assert_fold(train, evaluation, evaluation.session_date.min())
    except ValueError as exc:
        raise AblationContractError(str(exc)) from exc
    x_train, x_evaluation = train[columns].copy(), evaluation[columns].copy()
    if x_train.isna().any().any() or x_evaluation.isna().any().any():
        raise AblationContractError("Feature comparison contains missing values")
    return x_train, x_evaluation


def _labels(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    fold: dict[str, Any],
    task: str,
    role: str = "outer",
):
    if task == "return":
        return (
            train.relative_return_class.astype(int).to_numpy(),
            evaluation.relative_return_class.astype(int).to_numpy(),
            None,
        )
    if task != "risk":
        raise AblationContractError("Task must be 'return' or 'risk'")
    if role not in {"inner", "outer"}:
        raise AblationContractError("Risk label role must be 'inner' or 'outer'")
    saved = fold["tasks"]["risk"][role]
    boundaries = saved["risk_boundaries"]
    y_train = apply_risk_boundaries(train.risk_volatility_next_20d, boundaries)
    y_evaluation = apply_risk_boundaries(
        evaluation.risk_volatility_next_20d, boundaries
    )
    if np.bincount(y_train, minlength=3).tolist() != saved["train_class_counts"]:
        raise AblationContractError(f"{role.title()} training risk classes differ from frozen cutoffs")
    if np.bincount(y_evaluation, minlength=3).tolist() != saved["evaluation_class_counts"]:
        raise AblationContractError(f"{role.title()} evaluation risk classes differ from frozen cutoffs")
    return y_train, y_evaluation, boundaries


def _fit_predict(
    estimator: str,
    parameters: dict[str, Any],
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_evaluation: pd.DataFrame,
) -> np.ndarray:
    if estimator == "LogisticRegression":
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=parameters["C"], max_iter=1000, solver="lbfgs"),
        )
    elif estimator == "HistGradientBoosting":
        model = HistGradientBoostingClassifier(**parameters)
    else:
        raise AblationContractError(
            "Estimator must be 'LogisticRegression' or 'HistGradientBoosting'"
        )
    model.fit(x_train, y_train)
    classes = model.classes_ if estimator == "HistGradientBoosting" else model[-1].classes_
    if not np.array_equal(classes, [0, 1, 2]):
        raise AblationContractError("Fitted model class order differs from [0, 1, 2]")
    probabilities = model.predict_proba(x_evaluation)
    if not np.isfinite(probabilities).all() or not np.allclose(
        probabilities.sum(axis=1), 1.0
    ):
        raise AblationContractError("Model returned invalid class probabilities")
    return probabilities


def _parameters(protocol: dict[str, Any], estimator: str) -> list[dict[str, Any]]:
    budget = protocol["experiment_protocol"]["search_budget"]
    if estimator == "LogisticRegression":
        return [{"C": value} for value in budget["logistic_C"]]
    if estimator == "HistGradientBoosting":
        fixed = budget["hist_gbm_fixed"]
        if fixed.get("early_stopping") is not False:
            raise AblationContractError("HistGradientBoosting early stopping must remain disabled")
        return [
            {**fixed, "max_leaf_nodes": value}
            for value in budget["hist_gbm_max_leaf_nodes"]
        ]
    raise AblationContractError("Unsupported estimator")


def _primary_score(
    task: str,
    evaluation: pd.DataFrame,
    truth: np.ndarray,
    probabilities: np.ndarray,
) -> float:
    if task == "return":
        ranking = _return_ranking(evaluation, probabilities[:, 2] - probabilities[:, 0])
        score = ranking["mean_daily_spearman"]
        if score is None:
            raise AblationContractError("Return validation fold has no defined ranking score")
        return float(score)
    return float(
        f1_score(truth, probabilities.argmax(axis=1), labels=[0, 1, 2], average="macro", zero_division=0)
    )


def tune_on_inner_validation(
    task: str,
    estimator: str,
    parameter_grid: list[dict[str, Any]],
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_validation: pd.DataFrame,
    y_validation: np.ndarray,
    validation_rows: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select settings using inner training and validation inputs only."""

    if not parameter_grid:
        raise AblationContractError("Inner tuning parameter grid must not be empty")
    if len(x_train) != len(y_train) or len(x_validation) != len(y_validation):
        raise AblationContractError("Inner training/validation features and labels do not align")
    if len(validation_rows) != len(y_validation):
        raise AblationContractError("Inner validation rows and labels do not align")
    candidates = []
    for parameters in parameter_grid:
        probabilities = _fit_predict(
            estimator, parameters, x_train, y_train, x_validation
        )
        candidates.append(
            {
                "parameters": parameters,
                "primary_score": _primary_score(
                    task, validation_rows, y_validation, probabilities
                ),
            }
        )
    # max() keeps the first parameter setting when primary scores tie.
    selected = max(candidates, key=lambda row: row["primary_score"])["parameters"]
    return selected, candidates


def _outer_metrics(
    task: str,
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    y_train: np.ndarray,
    y_evaluation: np.ndarray,
    probabilities: np.ndarray,
    risk_boundaries: list[float] | None,
) -> dict[str, Any]:
    prediction = probabilities.argmax(axis=1)
    metrics: dict[str, Any] = {
        "macro_f1": float(
            f1_score(y_evaluation, prediction, labels=[0, 1, 2], average="macro", zero_division=0)
        ),
        "ordinal_mae": float(np.mean(np.abs(y_evaluation - prediction))),
        "confusion_matrix": confusion_matrix(y_evaluation, prediction, labels=[0, 1, 2]).tolist(),
        "training_class_prior_macro_f1": float(
            f1_score(
                y_evaluation,
                np.full(len(y_evaluation), int(np.argmax(np.bincount(y_train, minlength=3)))),
                labels=[0, 1, 2],
                average="macro",
                zero_division=0,
            )
        ),
    }
    if task == "return":
        model_ranking = _return_ranking(
            evaluation, probabilities[:, 2] - probabilities[:, 0]
        )
        momentum_ranking = _return_ranking(evaluation, evaluation.momentum_20d)
        metrics["mean_daily_spearman"] = model_ranking["mean_daily_spearman"]
        metrics["momentum_mean_daily_spearman"] = momentum_ranking[
            "mean_daily_spearman"
        ]
        metrics["defined_ranking_dates"] = model_ranking["defined_spearman_dates"]
    else:
        prior_class = int(np.argmax(np.bincount(y_train, minlength=3)))
        trailing_class = apply_risk_boundaries(evaluation.volatility_20d, risk_boundaries)
        metrics["high_recall"] = float(
            recall_score(y_evaluation, prediction, labels=[2], average="macro", zero_division=0)
        )
        metrics["high_to_low_count"] = int(((y_evaluation == 2) & (prediction == 0)).sum())
        metrics["high_outcomes"] = int((y_evaluation == 2).sum())
        metrics["trailing_volatility_macro_f1"] = float(
            f1_score(y_evaluation, trailing_class, labels=[0, 1, 2], average="macro", zero_division=0)
        )
        metrics["trailing_volatility_high_recall"] = float(
            recall_score(y_evaluation, trailing_class, labels=[2], average="macro", zero_division=0)
        )
        metrics["trailing_volatility_high_to_low_count"] = int(
            ((y_evaluation == 2) & (trailing_class == 0)).sum()
        )
        metrics["prior_high_to_low_count"] = int(
            ((y_evaluation == 2) & (prior_class == 0)).sum()
        )
    return metrics


def run_ablation_experiment(
    task: str,
    estimator: str,
    experiment_name: str,
    *,
    data_path: Path = DEFAULT_DATA,
    protocol_path: Path = DEFAULT_PROTOCOL,
    contract_path: Path = DEFAULT_CONTRACT,
    inventory_path: Path = DEFAULT_INVENTORY_JSON,
) -> dict[str, Any]:
    """Tune one feature set per fold and return its outer-fold evidence."""

    if task not in {"return", "risk"}:
        raise AblationContractError("Task must be 'return' or 'risk'")
    frame, _, protocol = verify_inputs(data_path, protocol_path)
    if sha256(data_path) != FROZEN_DATA_SHA256 or sha256(protocol_path) != FROZEN_PROTOCOL_SHA256:
        raise AblationContractError("Frozen Phase 4 input hashes changed")
    contract = _read_json(contract_path, "Phase 6.1 contract")
    metadata_path = Path(data_path).with_name("dataset_metadata.json")
    current_contract = build_ablation_contract_report(
        dataset_path=data_path,
        metadata_path=metadata_path,
        protocol_path=protocol_path,
    )
    if contract != current_contract:
        raise AblationContractError("Phase 6.1 contract is stale or incompatible")
    inventory = _read_json(inventory_path, "Phase 6.2 feature inventory")
    rebuilt_inventory, _ = build_feature_inventory_report(
        data_path, Path(data_path).with_name("dataset_metadata.json"), contract_path
    )
    if not same_inventory_content(inventory, rebuilt_inventory):
        raise AblationContractError("Phase 6.2 inventory content is stale or incompatible")
    plan = build_experiment_plan(inventory)
    selected = [item for item in plan if item["name"] == experiment_name]
    if len(selected) != 1:
        raise AblationContractError(f"Unknown predeclared experiment: {experiment_name}")
    experiment = selected[0]
    parameter_grid = _parameters(protocol, estimator)
    fold_results = []

    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, task, "inner")
        outer_train, outer_eval = fold_roles(frame, fold, task, "outer")
        assert_fold(inner_train, inner_eval, fold["inner_first"])
        assert_fold(outer_train, outer_eval, fold["outer_first"])
        inner_saved = fold["tasks"][task]["inner"]
        outer_saved = fold["tasks"][task]["outer"]
        if (
            len(inner_train) != inner_saved["train_rows"]
            or _hash_keys(inner_train) != inner_saved["train_keys_sha256"]
            or len(inner_eval) != inner_saved["evaluation_rows"]
            or _hash_keys(inner_eval) != inner_saved["evaluation_keys_sha256"]
            or len(outer_train) != outer_saved["train_rows"]
            or _hash_keys(outer_train) != outer_saved["train_keys_sha256"]
            or len(outer_eval) != outer_saved["evaluation_rows"]
            or _hash_keys(outer_eval) != outer_saved["evaluation_keys_sha256"]
        ):
            raise AblationContractError("Fold rows differ from the frozen protocol")

        x_inner_train, x_inner_eval = select_matched_features(
            inner_train, inner_eval, experiment["features"]
        )
        y_inner_train, y_inner_eval, _ = _labels(
            inner_train, inner_eval, fold, task, role="inner"
        )
        selected_parameters, candidates = tune_on_inner_validation(
            task,
            estimator,
            parameter_grid,
            x_inner_train,
            y_inner_train,
            x_inner_eval,
            y_inner_eval,
            inner_eval,
        )

        x_outer_train, x_outer_eval = select_matched_features(
            outer_train, outer_eval, experiment["features"]
        )
        y_outer_train, y_outer_eval, risk_boundaries = _labels(
            outer_train, outer_eval, fold, task
        )
        probabilities = _fit_predict(
            estimator,
            selected_parameters,
            x_outer_train,
            y_outer_train,
            x_outer_eval,
        )
        fold_results.append(
            {
                "fold": fold["fold"],
                "task": task,
                "estimator": estimator,
                "experiment": experiment["name"],
                "groups": experiment["groups"],
                "features": experiment["features"],
                "selected_parameters": selected_parameters,
                "inner_candidates": candidates,
                "inner_training_rows": len(inner_train),
                "inner_evaluation_rows": len(inner_eval),
                "outer_training_rows": len(outer_train),
                "outer_evaluation_rows": len(outer_eval),
                "coverage_change_vs_frozen_protocol_rows": {"train": 0, "evaluation": 0},
                "inner_training_keys_sha256": _hash_keys(inner_train),
                "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
                "outer_training_keys_sha256": _hash_keys(outer_train),
                "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
                "outer_first": fold["outer_first"],
                "outer_last": fold["outer_last"],
                "risk_boundaries": risk_boundaries,
                "metrics": _outer_metrics(
                    task,
                    outer_train,
                    outer_eval,
                    y_outer_train,
                    y_outer_eval,
                    probabilities,
                    risk_boundaries,
                ),
            }
        )

    return {
        "schema_version": 1,
        "stage": "phase_6_feature_ablation",
        "status": "complete",
        "task": task,
        "estimator": estimator,
        "experiment": experiment,
        "primary_metric": (
            "mean_daily_spearman" if task == "return" else "macro_f1"
        ),
        "selection_rule": (
            "Tune only on the frozen inner training/validation rows using the "
            "primary metric; select the first parameter setting on ties; fit "
            "once on outer training rows and score outer rows once."
        ),
        "comparison_rule": (
            "All feature sets use the exact task-specific row keys from the "
            "frozen Phase 4 protocol. Future outcomes and identifiers are not "
            "features; preprocessing is fitted only inside the training pipeline."
        ),
        "provenance": {
            "dataset_sha256": sha256(data_path),
            "protocol_sha256": sha256(protocol_path),
            "contract_sha256": sha256(contract_path),
            "inventory_sha256": sha256(inventory_path),
            "inventory_source_hashes_recorded": inventory.get("code_sha256", {}),
            "inventory_source_hashes_current": rebuilt_inventory.get("code_sha256", {}),
            "runner_code_sha256": sha256(__file__),
            "protocol_code_sha256": protocol["code_sha256"],
        },
        "folds": fold_results,
    }


def write_ablation_experiment(
    task: str,
    estimator: str,
    experiment_name: str,
    output_dir: Path,
    **inputs: Path,
) -> dict[str, Any]:
    """Write one new run package and refuse to overwrite any existing path."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite ablation evidence: {output_dir}")
    report = run_ablation_experiment(
        task, estimator, experiment_name, **inputs
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "ablation_run.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def build_runner_validation_report(
    contract_path: Path = DEFAULT_CONTRACT,
    inventory_path: Path = DEFAULT_INVENTORY_JSON,
) -> dict[str, Any]:
    """Validate the plan and frozen provenance without fitting a model."""

    contract = _read_json(contract_path, "Phase 6.1 contract")
    if contract.get("status") != "verified":
        raise AblationContractError("Phase 6.1 contract has not been verified")
    inventory = _read_json(inventory_path, "Phase 6.2 feature inventory")
    rebuilt, _ = build_feature_inventory_report(contract_path=contract_path)
    if not same_inventory_content(inventory, rebuilt):
        raise AblationContractError("Phase 6.2 inventory differs from current inputs")
    plan = build_experiment_plan(inventory)
    return {
        "schema_version": 1,
        "stage": "phase_6_step_6_3_runner_validation",
        "status": "validated",
        "input_identities": {
            "contract": {"path": str(contract_path), "sha256": sha256(contract_path)},
            "inventory": {"path": str(inventory_path), "sha256": sha256(inventory_path)},
        },
        "inventory_source_hashes": {
            "recorded_in_inventory": inventory.get("code_sha256", {}),
            "current": rebuilt["code_sha256"],
            "content_unchanged": True,
            "note": (
                "The inventory retains its generation-time source hash. Its "
                "package path has since been reorganized; all inventory data, "
                "formulas, groups, missingness, and input identities were "
                "rebuilt and matched before this validation report was written."
            ),
        },
        "runner_code_sha256": sha256(__file__),
        "groups": list(DEFAULT_GROUP_ORDER),
        "planned_experiments": plan,
        "tasks": ["return", "risk"],
        "estimators": ["LogisticRegression", "HistGradientBoosting"],
        "selection_and_leakage_rules": [
            "Frozen Phase 4 fold and task-specific row keys are reconstructed and checked.",
            "Task labels and fold-specific risk cutoffs are kept separate.",
            "Hyperparameter selection uses inner validation only; final fit uses outer training only.",
            "Every feature set is allowlisted and evaluated on matched rows.",
            "Generated run paths are new-only and reports include source/input hashes.",
        ],
        "model_fitting_performed": False,
    }


def write_runner_validation_report(
    output_path: Path = DEFAULT_RUN_PLAN,
    contract_path: Path = DEFAULT_CONTRACT,
    inventory_path: Path = DEFAULT_INVENTORY_JSON,
) -> dict[str, Any]:
    """Write the Step 6.3 validation plan without overwriting evidence."""

    output_path = Path(output_path)
    report = build_runner_validation_report(contract_path, inventory_path)
    if output_path.exists():
        saved_report = _read_json(output_path, "existing runner validation")
        if saved_report != report:
            raise FileExistsError(
                "Existing runner validation differs from current inputs; "
                "refusing to overwrite it"
            )
        return saved_report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report
