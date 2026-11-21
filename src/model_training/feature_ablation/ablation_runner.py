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
    build_protocol,
    load_and_audit,
)
from src.model_training.feature_ablation.ablation_contract import (
    DEFAULT_OUTPUT as DEFAULT_CONTRACT,
    build_ablation_contract_report,
)
from src.model_training.feature_ablation.feature_inventory import (
    DEFAULT_INVENTORY_JSON,
    build_feature_inventory_report,
    build_recovery_feature_inventory_report,
    same_inventory_content,
)


DEFAULT_RUN_PLAN = Path(
    "reports/model_evaluation/feature_ablation/v1/runner_validation.json"
)
DEFAULT_RECOVERY_DATASET = Path(
    "data/processed/model_inputs/phase6_recovery_v1/"
    "market_features_and_labels.csv"
)
DEFAULT_RECOVERY_METADATA = DEFAULT_RECOVERY_DATASET.with_name(
    "dataset_metadata.json"
)
DEFAULT_RECOVERY_PROTOCOL = Path(
    "reports/model_evaluation/phase6_recovery_v1/"
    "chronological_evaluation_protocol.json"
)
DEFAULT_RECOVERY_INVENTORY = Path(
    "reports/model_evaluation/phase6_recovery_v1/feature_inventory.json"
)
DEFAULT_RECOVERY_RUN_PLAN = Path(
    "reports/model_evaluation/phase6_recovery_v1/runner_validation.json"
)
DEFAULT_RECOVERY_MOMENTUM_OUTPUT = Path(
    "reports/model_evaluation/phase6_recovery_v1/momentum_ablation"
)
DEFAULT_RECOVERY_VOLATILITY_OUTPUT = Path(
    "reports/model_evaluation/phase6_recovery_v1/volatility_ablation"
)
RECOVERY_MOMENTUM_EXPERIMENTS = (
    "cumulative_momentum_plus_volatility_plus_downside_trend_plus_market_relative_plus_volume",
    "without_momentum",
)
RECOVERY_VOLATILITY_EXPERIMENTS = (
    "cumulative_momentum_plus_volatility_plus_downside_trend_plus_market_relative_plus_volume",
    "without_volatility",
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


def build_recovery_runner_validation_report(
    dataset_path: Path = DEFAULT_RECOVERY_DATASET,
    metadata_path: Path = DEFAULT_RECOVERY_METADATA,
    protocol_path: Path = DEFAULT_RECOVERY_PROTOCOL,
    inventory_path: Path = DEFAULT_RECOVERY_INVENTORY,
) -> dict[str, Any]:
    """Validate the recovery plan without fitting, tuning, or scoring a model.

    The original Phase 5 generated evidence is unavailable in this checkout, so
    this route deliberately validates only the separately versioned Phase 3/4
    recovery inputs and the verified Step 6.2 inventory. It is not a substitute
    for old Phase 5 results and it does not make a feature-performance claim.
    """

    dataset_path, metadata_path, protocol_path, inventory_path = map(
        Path, (dataset_path, metadata_path, protocol_path, inventory_path)
    )
    inventory = _read_json(inventory_path, "recovery Phase 6.2 feature inventory")
    rebuilt_inventory, _ = build_recovery_feature_inventory_report(
        dataset_path, metadata_path, protocol_path
    )
    if not same_inventory_content(inventory, rebuilt_inventory):
        raise AblationContractError(
            "Recovery Phase 6.2 inventory differs from its dataset or protocol"
        )
    if inventory.get("evidence_mode") != (
        "reconstructed_phase_3_and_4_inputs; original_phase_5_reports_unavailable"
    ):
        raise AblationContractError("Recovery inventory has an unexpected evidence mode")

    plan = build_experiment_plan(inventory)
    return {
        "schema_version": 1,
        "stage": "phase_6_step_6_3_runner_validation",
        "status": "validated",
        "evidence_mode": inventory["evidence_mode"],
        "input_identities": {
            **rebuilt_inventory["input_identities"],
            "inventory": {"path": str(inventory_path), "sha256": sha256(inventory_path)},
        },
        "runner_code_sha256": sha256(__file__),
        "groups": list(DEFAULT_GROUP_ORDER),
        "planned_experiments": plan,
        "tasks": ["return", "risk"],
        "estimators": ["LogisticRegression", "HistGradientBoosting"],
        "selection_and_leakage_rules": [
            "The rebuilt Phase 4 protocol must exactly match the recovery dataset.",
            "Task labels and fold-specific risk cutoffs stay separate.",
            "Future outcomes, identifiers, and unapproved fundamentals cannot become inputs.",
            "Later tuning uses inner validation only; final fitting uses outer training only.",
            "Every later feature set must use matched task-specific rows and a new output path.",
        ],
        "phase_5_comparison_recreated": False,
        "model_fitting_performed": False,
        "next_step": (
            "This validates the runner design only. Run market-group comparisons in "
            "Steps 6.4-6.8 after reviewing this report; do not use this plan as a "
            "model-performance result."
        ),
    }


def write_recovery_runner_validation_report(
    output_path: Path = DEFAULT_RECOVERY_RUN_PLAN,
    dataset_path: Path = DEFAULT_RECOVERY_DATASET,
    metadata_path: Path = DEFAULT_RECOVERY_METADATA,
    protocol_path: Path = DEFAULT_RECOVERY_PROTOCOL,
    inventory_path: Path = DEFAULT_RECOVERY_INVENTORY,
) -> dict[str, Any]:
    """Write one recovery validation report and refuse differing replacement."""

    output_path = Path(output_path)
    report = build_recovery_runner_validation_report(
        dataset_path, metadata_path, protocol_path, inventory_path
    )
    if output_path.exists():
        saved_report = _read_json(output_path, "existing recovery runner validation")
        if saved_report != report:
            raise FileExistsError(
                "Existing recovery runner validation differs from current inputs; "
                "choose a reviewed new version instead of overwriting it"
            )
        return saved_report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def _recovery_context(
    dataset_path: Path,
    metadata_path: Path,
    protocol_path: Path,
    inventory_path: Path,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load and independently re-check the separately versioned recovery inputs."""

    dataset_path, metadata_path, protocol_path, inventory_path = map(
        Path, (dataset_path, metadata_path, protocol_path, inventory_path)
    )
    frame, metadata = load_and_audit(dataset_path)
    saved_metadata = _read_json(metadata_path, "recovery dataset metadata")
    if saved_metadata != metadata:
        raise AblationContractError("Recovery dataset metadata differs from the audited data")
    protocol = _read_json(protocol_path, "recovery chronological protocol")
    if protocol.get("dataset_sha256") != sha256(dataset_path):
        raise AblationContractError("Recovery protocol refers to another dataset")
    if build_protocol(frame, metadata) != protocol:
        raise AblationContractError("Recovery protocol differs from reconstructed folds")
    inventory = _read_json(inventory_path, "recovery Phase 6.2 feature inventory")
    rebuilt_inventory, _ = build_recovery_feature_inventory_report(
        dataset_path, metadata_path, protocol_path
    )
    if not same_inventory_content(inventory, rebuilt_inventory):
        raise AblationContractError(
            "Recovery Phase 6.2 inventory differs from its dataset or protocol"
        )
    if inventory.get("evidence_mode") != (
        "reconstructed_phase_3_and_4_inputs; original_phase_5_reports_unavailable"
    ):
        raise AblationContractError("Recovery inventory has an unexpected evidence mode")
    return frame, protocol, inventory, rebuilt_inventory


def run_recovery_ablation_experiment(
    task: str,
    estimator: str,
    experiment_name: str,
    *,
    dataset_path: Path = DEFAULT_RECOVERY_DATASET,
    metadata_path: Path = DEFAULT_RECOVERY_METADATA,
    protocol_path: Path = DEFAULT_RECOVERY_PROTOCOL,
    inventory_path: Path = DEFAULT_RECOVERY_INVENTORY,
) -> dict[str, Any]:
    """Fit one verified recovery ablation using inner-only tuning.

    This deliberately uses the separately named Phase 6.2 recovery evidence.
    It does not assert that unavailable original Phase 5 generated reports have
    been recreated.
    """

    if task not in {"return", "risk"}:
        raise AblationContractError("Task must be 'return' or 'risk'")
    frame, protocol, inventory, rebuilt_inventory = _recovery_context(
        dataset_path, metadata_path, protocol_path, inventory_path
    )
    selected = [
        item
        for item in build_experiment_plan(inventory)
        if item["name"] == experiment_name
    ]
    if len(selected) != 1:
        raise AblationContractError(f"Unknown predeclared experiment: {experiment_name}")
    experiment = selected[0]
    parameter_grid = _parameters(protocol, estimator)
    fold_results = []

    for fold in protocol["folds"]:
        try:
            inner_train, inner_evaluation = fold_roles(frame, fold, task, "inner")
            outer_train, outer_evaluation = fold_roles(frame, fold, task, "outer")
        except ValueError as exc:
            raise AblationContractError(str(exc)) from exc
        assert_fold(inner_train, inner_evaluation, fold["inner_first"])
        assert_fold(outer_train, outer_evaluation, fold["outer_first"])
        for role, train, evaluation in (
            ("inner", inner_train, inner_evaluation),
            ("outer", outer_train, outer_evaluation),
        ):
            saved = fold["tasks"][task][role]
            if (
                len(train) != saved["train_rows"]
                or _hash_keys(train) != saved["train_keys_sha256"]
                or len(evaluation) != saved["evaluation_rows"]
                or _hash_keys(evaluation) != saved["evaluation_keys_sha256"]
            ):
                raise AblationContractError("Fold rows differ from the recovery protocol")

        x_inner_train, x_inner_evaluation = select_matched_features(
            inner_train, inner_evaluation, experiment["features"]
        )
        y_inner_train, y_inner_evaluation, _ = _labels(
            inner_train, inner_evaluation, fold, task, role="inner"
        )
        selected_parameters, candidates = tune_on_inner_validation(
            task,
            estimator,
            parameter_grid,
            x_inner_train,
            y_inner_train,
            x_inner_evaluation,
            y_inner_evaluation,
            inner_evaluation,
        )
        x_outer_train, x_outer_evaluation = select_matched_features(
            outer_train, outer_evaluation, experiment["features"]
        )
        y_outer_train, y_outer_evaluation, risk_boundaries = _labels(
            outer_train, outer_evaluation, fold, task, role="outer"
        )
        probabilities = _fit_predict(
            estimator,
            selected_parameters,
            x_outer_train,
            y_outer_train,
            x_outer_evaluation,
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
                "inner_evaluation_rows": len(inner_evaluation),
                "outer_training_rows": len(outer_train),
                "outer_evaluation_rows": len(outer_evaluation),
                "coverage_change_vs_protocol_rows": {"train": 0, "evaluation": 0},
                "inner_training_keys_sha256": _hash_keys(inner_train),
                "inner_evaluation_keys_sha256": _hash_keys(inner_evaluation),
                "outer_training_keys_sha256": _hash_keys(outer_train),
                "outer_evaluation_keys_sha256": _hash_keys(outer_evaluation),
                "outer_first": fold["outer_first"],
                "outer_last": fold["outer_last"],
                "risk_boundaries": risk_boundaries,
                "metrics": _outer_metrics(
                    task,
                    outer_train,
                    outer_evaluation,
                    y_outer_train,
                    y_outer_evaluation,
                    probabilities,
                    risk_boundaries,
                ),
            }
        )

    return {
        "schema_version": 1,
        "stage": "phase_6_recovery_feature_ablation",
        "status": "complete",
        "evidence_mode": inventory["evidence_mode"],
        "task": task,
        "estimator": estimator,
        "experiment": experiment,
        "primary_metric": "mean_daily_spearman" if task == "return" else "macro_f1",
        "selection_rule": (
            "Tune only on the saved inner training/validation rows using the primary "
            "metric; choose the first setting on a tie; refit once on outer training "
            "rows and score outer rows once."
        ),
        "comparison_rule": (
            "Each feature set uses the exact same task-specific recovery-protocol row "
            "keys. Future outcomes, identifiers, and unapproved fundamentals are not features."
        ),
        "phase_5_comparison_recreated": False,
        "provenance": {
            "dataset_sha256": sha256(dataset_path),
            "metadata_sha256": sha256(metadata_path),
            "protocol_sha256": sha256(protocol_path),
            "inventory_sha256": sha256(inventory_path),
            "inventory_source_hashes_recorded": inventory.get("code_sha256", {}),
            "inventory_source_hashes_current": rebuilt_inventory.get("code_sha256", {}),
            "runner_code_sha256": sha256(__file__),
            "protocol_code_sha256": protocol["code_sha256"],
        },
        "folds": fold_results,
    }


def _momentum_decision(
    task: str,
    mean_difference: float,
    fold_differences: list[float],
    *,
    mean_high_recall_difference: float | None = None,
    high_to_low_difference: int | None = None,
) -> str:
    """Apply the predeclared Phase 6.4 evidence rule, without picking a model."""

    positive_folds = sum(value > 0 for value in fold_differences)
    nonpositive_folds = sum(value <= 0 for value in fold_differences)
    if mean_difference <= 0 and nonpositive_folds >= 3:
        return "reject"
    if mean_difference > 0 and positive_folds >= 3:
        if task == "risk" and (
            mean_high_recall_difference is None
            or high_to_low_difference is None
            or mean_high_recall_difference < 0
            or high_to_low_difference > 0
        ):
            return "inconclusive"
        return "retain"
    return "inconclusive"


def summarize_momentum_comparison(
    task: str, with_momentum: dict[str, Any], without_momentum: dict[str, Any]
) -> dict[str, Any]:
    """Compare paired outer-fold results and make fold variation visible."""

    if task not in {"return", "risk"}:
        raise AblationContractError("Task must be 'return' or 'risk'")
    if with_momentum.get("task") != task or without_momentum.get("task") != task:
        raise AblationContractError("Momentum comparison reports have the wrong task")
    if with_momentum.get("estimator") != without_momentum.get("estimator"):
        raise AblationContractError("Momentum comparison must keep the estimator fixed")
    full = {entry["fold"]: entry for entry in with_momentum["folds"]}
    excluded = {entry["fold"]: entry for entry in without_momentum["folds"]}
    if not full or set(full) != set(excluded):
        raise AblationContractError("Momentum comparison requires the same nonempty folds")
    primary_metric = "mean_daily_spearman" if task == "return" else "macro_f1"
    fold_differences = []
    coverage = []
    for fold in sorted(full):
        first, second = full[fold], excluded[fold]
        comparable_keys = (
            "outer_training_rows",
            "outer_evaluation_rows",
            "outer_training_keys_sha256",
            "outer_evaluation_keys_sha256",
            "outer_first",
            "outer_last",
        )
        if any(first[key] != second[key] for key in comparable_keys):
            raise AblationContractError("Momentum comparison changed fold coverage")
        first_score = first["metrics"][primary_metric]
        second_score = second["metrics"][primary_metric]
        if first_score is None or second_score is None:
            raise AblationContractError("Momentum comparison has an undefined primary metric")
        fold_differences.append(
            {
                "fold": fold,
                "with_momentum": float(first_score),
                "without_momentum": float(second_score),
                "difference": float(first_score - second_score),
            }
        )
        coverage.append({key: first[key] for key in comparable_keys})

    differences = [item["difference"] for item in fold_differences]
    summary: dict[str, Any] = {
        "task": task,
        "estimator": with_momentum["estimator"],
        "primary_metric": primary_metric,
        "comparison": "full_allowlisted_market_features versus the same set without momentum",
        "fold_metrics": fold_differences,
        "mean_with_momentum": float(np.mean([item["with_momentum"] for item in fold_differences])),
        "mean_without_momentum": float(np.mean([item["without_momentum"] for item in fold_differences])),
        "mean_difference": float(np.mean(differences)),
        "positive_fold_count": sum(value > 0 for value in differences),
        "nonpositive_fold_count": sum(value <= 0 for value in differences),
        "coverage": coverage,
        "decision_rule": (
            "Retain only if the mean primary-metric difference is positive and at "
            "least three of four fold differences are positive. Reject if the mean "
            "difference is nonpositive and at least three folds are nonpositive; "
            "otherwise mark inconclusive."
        ),
    }
    if task == "risk":
        recall_differences = [
            float(full[fold]["metrics"]["high_recall"] - excluded[fold]["metrics"]["high_recall"])
            for fold in sorted(full)
        ]
        high_to_low_difference = int(
            sum(full[fold]["metrics"]["high_to_low_count"] for fold in full)
            - sum(excluded[fold]["metrics"]["high_to_low_count"] for fold in excluded)
        )
        summary["risk_guardrails"] = {
            "mean_high_recall_difference": float(np.mean(recall_differences)),
            "high_to_low_count_difference": high_to_low_difference,
            "rule": (
                "A primary-metric gain is not retained if mean High-risk recall falls "
                "or the total High-predicted-Low count rises."
            ),
        }
        summary["decision"] = _momentum_decision(
            task,
            summary["mean_difference"],
            differences,
            mean_high_recall_difference=summary["risk_guardrails"]["mean_high_recall_difference"],
            high_to_low_difference=high_to_low_difference,
        )
    else:
        summary["decision"] = _momentum_decision(task, summary["mean_difference"], differences)
    return summary


def write_recovery_momentum_ablation_report(
    output_dir: Path = DEFAULT_RECOVERY_MOMENTUM_OUTPUT,
    *,
    dataset_path: Path = DEFAULT_RECOVERY_DATASET,
    metadata_path: Path = DEFAULT_RECOVERY_METADATA,
    protocol_path: Path = DEFAULT_RECOVERY_PROTOCOL,
    inventory_path: Path = DEFAULT_RECOVERY_INVENTORY,
) -> dict[str, Any]:
    """Run the Phase 6.4 paired momentum test and write a new-only evidence package."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite momentum evidence: {output_dir}")
    inputs = {
        "dataset_path": dataset_path,
        "metadata_path": metadata_path,
        "protocol_path": protocol_path,
        "inventory_path": inventory_path,
    }
    runs: dict[str, dict[str, Any]] = {}
    for task in ("return", "risk"):
        for experiment in RECOVERY_MOMENTUM_EXPERIMENTS:
            runs[f"{task}_{experiment}"] = run_recovery_ablation_experiment(
                task, "HistGradientBoosting", experiment, **inputs
            )
    task_summaries = {
        task: summarize_momentum_comparison(
            task,
            runs[f"{task}_{RECOVERY_MOMENTUM_EXPERIMENTS[0]}"],
            runs[f"{task}_{RECOVERY_MOMENTUM_EXPERIMENTS[1]}"],
        )
        for task in ("return", "risk")
    }
    report = {
        "schema_version": 1,
        "stage": "phase_6_step_6_4_momentum_ablation",
        "status": "complete",
        "evidence_mode": runs["return_" + RECOVERY_MOMENTUM_EXPERIMENTS[0]]["evidence_mode"],
        "estimator": "HistGradientBoosting",
        "experiments": list(RECOVERY_MOMENTUM_EXPERIMENTS),
        "task_summaries": task_summaries,
        "limitations": [
            "This is recovery evidence from the separately versioned Phase 6.2 dataset; unavailable original Phase 5 result files were not recreated.",
            "The 2024-2025 period remains excluded from development selection.",
            "This report is development evidence, not an untouched-test, trading, or portfolio result.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, run in runs.items():
        (output_dir / f"{name}.json").write_text(
            json.dumps(run, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    (output_dir / "momentum_ablation_summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def summarize_volatility_comparison(
    task: str, with_volatility: dict[str, Any], without_volatility: dict[str, Any]
) -> dict[str, Any]:
    """Compare paired outer-fold results for the approved volatility group."""

    if task not in {"return", "risk"}:
        raise AblationContractError("Task must be 'return' or 'risk'")
    if with_volatility.get("task") != task or without_volatility.get("task") != task:
        raise AblationContractError("Volatility comparison reports have the wrong task")
    if with_volatility.get("estimator") != without_volatility.get("estimator"):
        raise AblationContractError("Volatility comparison must keep the estimator fixed")
    full = {entry["fold"]: entry for entry in with_volatility["folds"]}
    excluded = {entry["fold"]: entry for entry in without_volatility["folds"]}
    if not full or set(full) != set(excluded):
        raise AblationContractError("Volatility comparison requires the same nonempty folds")
    primary_metric = "mean_daily_spearman" if task == "return" else "macro_f1"
    fold_differences = []
    coverage = []
    for fold in sorted(full):
        first, second = full[fold], excluded[fold]
        comparable_keys = (
            "outer_training_rows",
            "outer_evaluation_rows",
            "outer_training_keys_sha256",
            "outer_evaluation_keys_sha256",
            "outer_first",
            "outer_last",
        )
        if any(first[key] != second[key] for key in comparable_keys):
            raise AblationContractError("Volatility comparison changed fold coverage")
        first_score = first["metrics"][primary_metric]
        second_score = second["metrics"][primary_metric]
        if first_score is None or second_score is None:
            raise AblationContractError("Volatility comparison has an undefined primary metric")
        fold_differences.append(
            {
                "fold": fold,
                "with_volatility": float(first_score),
                "without_volatility": float(second_score),
                "difference": float(first_score - second_score),
            }
        )
        coverage.append({key: first[key] for key in comparable_keys})

    differences = [item["difference"] for item in fold_differences]
    summary: dict[str, Any] = {
        "task": task,
        "estimator": with_volatility["estimator"],
        "primary_metric": primary_metric,
        "comparison": "full_allowlisted_market_features versus the same set without volatility",
        "fold_metrics": fold_differences,
        "mean_with_volatility": float(np.mean([item["with_volatility"] for item in fold_differences])),
        "mean_without_volatility": float(np.mean([item["without_volatility"] for item in fold_differences])),
        "mean_difference": float(np.mean(differences)),
        "positive_fold_count": sum(value > 0 for value in differences),
        "nonpositive_fold_count": sum(value <= 0 for value in differences),
        "coverage": coverage,
        "decision_rule": (
            "Retain only if the mean primary-metric difference is positive and at "
            "least three of four fold differences are positive. Reject if the mean "
            "difference is nonpositive and at least three folds are nonpositive; "
            "otherwise mark inconclusive."
        ),
    }
    if task == "risk":
        recall_differences = [
            float(full[fold]["metrics"]["high_recall"] - excluded[fold]["metrics"]["high_recall"])
            for fold in sorted(full)
        ]
        high_to_low_difference = int(
            sum(full[fold]["metrics"]["high_to_low_count"] for fold in full)
            - sum(excluded[fold]["metrics"]["high_to_low_count"] for fold in excluded)
        )
        summary["risk_guardrails"] = {
            "mean_high_recall_difference": float(np.mean(recall_differences)),
            "high_to_low_count_difference": high_to_low_difference,
            "rule": (
                "A primary-metric gain is not retained if mean High-risk recall falls "
                "or the total High-predicted-Low count rises."
            ),
        }
        summary["decision"] = _momentum_decision(
            task,
            summary["mean_difference"],
            differences,
            mean_high_recall_difference=summary["risk_guardrails"]["mean_high_recall_difference"],
            high_to_low_difference=high_to_low_difference,
        )
    else:
        summary["decision"] = _momentum_decision(task, summary["mean_difference"], differences)
    return summary


def write_recovery_volatility_ablation_report(
    output_dir: Path = DEFAULT_RECOVERY_VOLATILITY_OUTPUT,
    *,
    dataset_path: Path = DEFAULT_RECOVERY_DATASET,
    metadata_path: Path = DEFAULT_RECOVERY_METADATA,
    protocol_path: Path = DEFAULT_RECOVERY_PROTOCOL,
    inventory_path: Path = DEFAULT_RECOVERY_INVENTORY,
) -> dict[str, Any]:
    """Run the Phase 6.5 paired volatility test and write new-only evidence."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite volatility evidence: {output_dir}")
    inputs = {
        "dataset_path": dataset_path,
        "metadata_path": metadata_path,
        "protocol_path": protocol_path,
        "inventory_path": inventory_path,
    }
    runs: dict[str, dict[str, Any]] = {}
    for task in ("return", "risk"):
        for experiment in RECOVERY_VOLATILITY_EXPERIMENTS:
            runs[f"{task}_{experiment}"] = run_recovery_ablation_experiment(
                task, "HistGradientBoosting", experiment, **inputs
            )
    task_summaries = {
        task: summarize_volatility_comparison(
            task,
            runs[f"{task}_{RECOVERY_VOLATILITY_EXPERIMENTS[0]}"],
            runs[f"{task}_{RECOVERY_VOLATILITY_EXPERIMENTS[1]}"],
        )
        for task in ("return", "risk")
    }
    report = {
        "schema_version": 1,
        "stage": "phase_6_step_6_5_volatility_ablation",
        "status": "complete",
        "evidence_mode": runs["return_" + RECOVERY_VOLATILITY_EXPERIMENTS[0]]["evidence_mode"],
        "estimator": "HistGradientBoosting",
        "experiments": list(RECOVERY_VOLATILITY_EXPERIMENTS),
        "task_summaries": task_summaries,
        "limitations": [
            "This is recovery evidence from the separately versioned Phase 6.2 dataset; unavailable original Phase 5 result files were not recreated.",
            "The 2024-2025 period remains excluded from development selection.",
            "This report is development evidence, not an untouched-test, trading, or portfolio result.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, run in runs.items():
        (output_dir / f"{name}.json").write_text(
            json.dumps(run, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    (output_dir / "volatility_ablation_summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report
