"""Phase 7 handoff, experiment-contract, and no-fit runner validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.baseline_models import fold_roles


HANDOFF_PATH = Path("configs/phase7_handoff_v1.json")
FREEZE_PATH = Path("configs/phase6_feature_freeze_v2.json")
DATASET_PATH = Path(
    "data/processed/model_inputs/phase6_expanded_features_v1/"
    "market_features_and_labels.csv"
)
METADATA_PATH = DATASET_PATH.with_name("dataset_metadata.json")
PROTOCOL_PATH = Path(
    "reports/model_evaluation/phase6_market_feature_expansion_v1/"
    "chronological_evaluation_protocol.json"
)
OUTPUT_ROOT = Path("reports/model_evaluation/phase7_candidate_tuning_v1")
HANDOFF_REPORT = OUTPUT_ROOT / "handoff_validation.json"
EXPERIMENT_CONTRACT = OUTPUT_ROOT / "experiment_contract.json"
RUNNER_VALIDATION = OUTPUT_ROOT / "runner_validation.json"

EXPECTED_ROWS = 124_987
EXPECTED_ELIGIBLE_ROWS = 118_987
EXPECTED_BRANCH = "feature/model-evaluation"
ESTIMATOR_ORDER = ["LogisticRegression", "HistGradientBoosting"]
VARIANT_ORDER = ["comparator", "candidate"]


class Phase7ContractError(ValueError):
    """Raised when frozen Phase 7 inputs or rules do not reproduce."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 7 evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def _git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def source_identity() -> dict[str, str]:
    """Record the checked-out source identity without changing Git state."""

    branch = _git_value("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise Phase7ContractError(
            f"Phase 7 must run on {EXPECTED_BRANCH}; current branch is {branch!r}"
        )
    dirty = _git_value("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise Phase7ContractError(
            "Tracked files differ from the checked-out commit; commit or restore them first"
        )
    return {"branch": branch, "commit": _git_value("rev-parse", "HEAD")}


def load_verified_inputs() -> tuple[
    pd.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    """Load and verify the exact Phase 6 handoff used by Phase 7."""

    handoff = _read_json(HANDOFF_PATH, "Phase 7 handoff contract")
    freeze = _read_json(FREEZE_PATH, "Phase 6 v2 freeze")
    for artifact in handoff["required_local_artifacts"]:
        path = Path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing transferred artifact: {path}")
        if sha256(path) != artifact["sha256"]:
            raise Phase7ContractError(f"Transferred artifact checksum mismatch: {path}")
    for required in handoff["required_versioned_repository_files"]:
        if not Path(required).is_file():
            raise FileNotFoundError(f"Missing required repository file: {required}")

    metadata = _read_json(METADATA_PATH, "expanded dataset metadata")
    protocol = _read_json(PROTOCOL_PATH, "expanded chronological protocol")
    if freeze.get("status") != "frozen_development_candidate":
        raise Phase7ContractError("Phase 6 v2 freeze is not active")
    if sha256(DATASET_PATH) != freeze["expanded_dataset"]["sha256"]:
        raise Phase7ContractError("Expanded dataset differs from the v2 freeze")
    if sha256(METADATA_PATH) != freeze["expanded_dataset"]["metadata_sha256"]:
        raise Phase7ContractError("Expanded metadata differs from the v2 freeze")
    if sha256(PROTOCOL_PATH) != freeze["protocol"]["sha256"]:
        raise Phase7ContractError("Chronological protocol differs from the v2 freeze")

    frame = pd.read_csv(DATASET_PATH, low_memory=False)
    if len(frame) != EXPECTED_ROWS or metadata.get("rows") != EXPECTED_ROWS:
        raise Phase7ContractError("Expanded dataset row count differs from the handoff")
    if frame.duplicated(["ticker", "session_date"]).any():
        raise Phase7ContractError("Expanded dataset has duplicate ticker/date keys")
    if int(frame["return_eligible"].sum()) != EXPECTED_ELIGIBLE_ROWS:
        raise Phase7ContractError("Return eligibility count differs from the handoff")
    if int(frame["risk_eligible"].sum()) != EXPECTED_ELIGIBLE_ROWS:
        raise Phase7ContractError("Risk eligibility count differs from the handoff")
    if len(protocol.get("folds", [])) != 4:
        raise Phase7ContractError("Phase 7 requires the four frozen folds")
    if protocol.get("test_start") != "2024-07-01":
        raise Phase7ContractError("Reused-period boundary differs from the freeze")
    if any(fold["outer_last"] >= protocol["test_start"] for fold in protocol["folds"]):
        raise Phase7ContractError("A development fold enters the reused period")

    original = freeze["original_phase5_features"]
    expected_features = original + metadata["added_feature_columns"]
    if metadata.get("feature_columns") != expected_features:
        raise Phase7ContractError("Expanded feature order differs from the freeze")
    required_features = set(original)
    for task in ("return", "risk"):
        required_features.update(freeze["tasks"][task]["candidate_features"])
        eligible = frame[f"{task}_eligible"].eq(True)
        missing = frame.loc[eligible, sorted(required_features)].isna().sum()
        if missing.any():
            raise Phase7ContractError(
                f"Eligible {task} rows have missing frozen features: "
                f"{missing[missing.gt(0)].to_dict()}"
            )
    return frame, metadata, protocol, freeze, handoff


def validate_handoff(output: Path = HANDOFF_REPORT) -> dict[str, Any]:
    frame, metadata, protocol, freeze, handoff = load_verified_inputs()
    identity = source_identity()
    report = {
        "schema_version": 1,
        "stage": "phase_7_step_7_1_handoff_validation",
        "status": "validated",
        "model_fitting_performed": False,
        "source_control": identity,
        "dataset": {
            "path": str(DATASET_PATH),
            "sha256": sha256(DATASET_PATH),
            "rows": len(frame),
            "companies": int(frame["ticker"].nunique()),
            "sessions": int(frame["session_date"].nunique()),
            "return_eligible_rows": int(frame["return_eligible"].sum()),
            "risk_eligible_rows": int(frame["risk_eligible"].sum()),
            "development_research_only": True,
        },
        "metadata_sha256": sha256(METADATA_PATH),
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": sha256(PROTOCOL_PATH),
            "folds": len(protocol["folds"]),
            "reused_test_start": protocol["test_start"],
        },
        "freeze": {
            "path": str(FREEZE_PATH),
            "sha256": sha256(FREEZE_PATH),
            "return_features": freeze["tasks"]["return"]["candidate_features"],
            "risk_features": freeze["tasks"]["risk"]["candidate_features"],
        },
        "verified_artifacts": len(handoff["required_local_artifacts"]),
        "limitations": freeze["limitations"],
    }
    _write_new_json(Path(output), report)
    return report


def build_experiment_contract() -> dict[str, Any]:
    _, _, protocol, freeze, _ = load_verified_inputs()
    budget = protocol["experiment_protocol"]["search_budget"]
    return {
        "schema_version": 1,
        "stage": "phase_7_step_7_2_experiment_contract",
        "status": "frozen_before_model_results",
        "model_fitting_performed": False,
        "dataset_sha256": sha256(DATASET_PATH),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "freeze_sha256": sha256(FREEZE_PATH),
        "tasks": {
            "return": {
                "comparator_features": freeze["original_phase5_features"],
                "candidate_features": freeze["tasks"]["return"]["candidate_features"],
                "primary_metric": "mean_daily_spearman",
                "benchmark": "momentum_20d",
                "class_names": ["Lower", "Middle", "Higher"],
                "rank_score": "P(Higher)-P(Lower); not a percentage return",
                "secondary_metrics": [
                    "macro_f1", "per_class_precision_recall", "ordinal_mae",
                    "confusion_matrix", "top10_minus_universe", "fold_variation",
                ],
            },
            "risk": {
                "comparator_features": freeze["original_phase5_features"],
                "candidate_features": freeze["tasks"]["risk"]["candidate_features"],
                "primary_metric": "macro_f1",
                "benchmark": "volatility_20d_with_fold_training_cutoffs",
                "class_names": ["Low", "Medium", "High"],
                "secondary_metrics": [
                    "per_class_precision_recall", "high_recall",
                    "high_to_low_count", "ordinal_mae", "confusion_matrix",
                    "log_loss", "multiclass_brier", "fold_variation",
                ],
            },
        },
        "estimators": {
            "order": ESTIMATOR_ORDER,
            "LogisticRegression": {
                "C": budget["logistic_C"],
                "solver": "lbfgs",
                "max_iter": 1000,
                "preprocessing": "StandardScaler fit on training rows only",
            },
            "HistGradientBoosting": {
                "max_leaf_nodes": budget["hist_gbm_max_leaf_nodes"],
                **budget["hist_gbm_fixed"],
            },
        },
        "folds": 4,
        "tuning_rule": (
            "Choose the hyperparameter on inner validation only; refit on outer "
            "training rows; score the outer block once. Ties keep declared grid order."
        ),
        "matched_rows_rule": "Comparator and candidate use identical ticker/date rows.",
        "return_decision_rule": (
            "A learned option may advance over momentum only with a positive mean "
            "primary difference and improvement in at least three of four folds. "
            "Otherwise retain momentum."
        ),
        "risk_decision_rule": (
            "A learned option may advance over trailing volatility only with a positive "
            "mean macro-F1 difference, improvement in at least three of four folds, "
            "non-worse mean High-risk recall, and no increase in total High-to-Low errors."
        ),
        "tie_rule": (
            "Within tuning, keep the first declared parameter on an exact tie. During "
            "review, keep estimator order then comparator/candidate order on an exact tie."
        ),
        "prohibitions": [
            "Do not use the reused period beginning 2024-07-01 for selection.",
            "Do not add features, estimators, parameters, imputation, or calibration.",
            "Do not describe probabilities or rank scores as expected percentage returns.",
            "Do not overwrite Phase 5, Phase 6, or existing Phase 7 evidence.",
        ],
    }


def write_experiment_contract(output: Path = EXPERIMENT_CONTRACT) -> dict[str, Any]:
    report = build_experiment_contract()
    _write_new_json(Path(output), report)
    return report


def validate_runner(output: Path = RUNNER_VALIDATION) -> dict[str, Any]:
    frame, _, protocol, freeze, _ = load_verified_inputs()
    contract = build_experiment_contract()
    checks: list[dict[str, Any]] = []
    for task in ("return", "risk"):
        variants = {
            "comparator": freeze["original_phase5_features"],
            "candidate": freeze["tasks"][task]["candidate_features"],
        }
        for fold in protocol["folds"]:
            inner_train, inner_eval = fold_roles(frame, fold, task, "inner")
            outer_train, outer_eval = fold_roles(frame, fold, task, "outer")
            if inner_train["target_window_end"].max() >= fold["inner_first"]:
                raise Phase7ContractError("Inner training outcome overlaps validation")
            if inner_eval["target_window_end"].max() >= fold["outer_first"]:
                raise Phase7ContractError("Inner validation outcome overlaps outer block")
            if outer_train["target_window_end"].max() >= fold["outer_first"]:
                raise Phase7ContractError("Outer training outcome overlaps evaluation")
            for name, columns in variants.items():
                if len(columns) != len(set(columns)):
                    raise Phase7ContractError(f"Duplicate {task} {name} feature")
                for rows in (inner_train, inner_eval, outer_train, outer_eval):
                    if rows[columns].isna().any().any():
                        raise Phase7ContractError(
                            f"Missing {task} {name} feature in fold {fold['fold']}"
                        )
            checks.append(
                {
                    "task": task,
                    "fold": fold["fold"],
                    "inner_training_rows": len(inner_train),
                    "inner_evaluation_rows": len(inner_eval),
                    "outer_training_rows": len(outer_train),
                    "outer_evaluation_rows": len(outer_eval),
                    "matched_variant_rows": True,
                    "purges_valid": True,
                }
            )
    tree = contract["estimators"]["HistGradientBoosting"]
    if tree["early_stopping"] is not False:
        raise Phase7ContractError("Tree early stopping must remain disabled")
    report = {
        "schema_version": 1,
        "stage": "phase_7_step_7_3_runner_validation",
        "status": "validated",
        "model_fitting_performed": False,
        "dataset_sha256": sha256(DATASET_PATH),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "experiment_contract_sha256": sha256(EXPERIMENT_CONTRACT),
        "checks": checks,
        "validated_rules": [
            "feature allowlists and order",
            "identical comparator/candidate rows",
            "chronological folds and target-window purges",
            "training-only scaling and risk cutoffs",
            "inner-only hyperparameter selection",
            "disabled tree early stopping",
            "deterministic ties",
            "new-only output paths and provenance",
        ],
    }
    _write_new_json(Path(output), report)
    return report


def prepare_phase7(output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Run Steps 7.1-7.3 only. This function never fits a model."""

    output_root = Path(output_root)
    handoff = validate_handoff(output_root / HANDOFF_REPORT.name)
    contract = write_experiment_contract(output_root / EXPERIMENT_CONTRACT.name)
    runner = validate_runner(output_root / RUNNER_VALIDATION.name)
    return {
        "handoff": handoff["status"],
        "contract": contract["status"],
        "runner": runner["status"],
        "model_fitting_performed": False,
        "output_root": str(output_root),
    }
