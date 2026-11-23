"""Controlled Phase 6.9 comparisons for two predeclared market-feature groups."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.feature_engineering.build_feature_dataset import sha256
from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.phase6_expansion_features import (
    EXPANSION_FEATURE_COLUMNS as ADDED_FEATURE_COLUMNS,
    EXPANSION_GROUPS,
)
from src.model_training.baseline_models import fold_roles
from src.model_training.chronological_evaluation_protocol import (
    _hash_keys,
    assert_fold,
    run as build_parent_protocol,
)
from src.model_training.feature_ablation.ablation_runner import (
    AblationContractError,
    _fit_predict,
    _labels,
    _outer_metrics,
    _parameters,
    _summarize_feature_group_comparison,
    tune_on_inner_validation,
)
from src.model_training.feature_ablation.phase5_continuation import (
    DATASET as PHASE5_DATASET,
    EXPECTED_DATASET_SHA256 as EXPECTED_PHASE5_DATASET_SHA256,
    EXPECTED_METADATA_SHA256 as EXPECTED_PHASE5_METADATA_SHA256,
    EXPECTED_PROTOCOL_SHA256 as EXPECTED_PHASE5_PROTOCOL_SHA256,
    METADATA as PHASE5_METADATA,
    PROTOCOL as PHASE5_PROTOCOL,
)
from src.target_engineering.build_phase6_expanded_dataset import (
    DEFAULT_OUTPUT as EXPANDED_DATASET_ROOT,
    EXPANDED_FEATURE_COLUMNS,
    build_expanded_dataset,
)


EXPERIMENT_ID = "phase6_market_feature_expansion_v1"
OUTPUT_ROOT = Path("reports/model_evaluation") / EXPERIMENT_ID
DATASET = EXPANDED_DATASET_ROOT / "market_features_and_labels.csv"
METADATA = EXPANDED_DATASET_ROOT / "dataset_metadata.json"
PROTOCOL = OUTPUT_ROOT / "chronological_evaluation_protocol.json"
VALIDATION = OUTPUT_ROOT / "expansion_validation.json"
CROSS_SECTIONAL_OUTPUT = OUTPUT_ROOT / "cross_sectional_relative_strength"
MARKET_REGIME_OUTPUT = OUTPUT_ROOT / "market_regime"
ESTIMATOR = "HistGradientBoosting"


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_expanded_dataset() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verify lineage, schema, row coverage, and feature completeness."""

    metadata = _load_json(METADATA, "expanded dataset metadata")
    if sha256(DATASET) != metadata.get("output_sha256"):
        raise AblationContractError("Expanded dataset checksum differs from metadata")
    if metadata.get("parent_dataset_sha256") != EXPECTED_PHASE5_DATASET_SHA256:
        raise AblationContractError("Expanded dataset does not descend from Phase 5 data")
    if metadata.get("parent_metadata_sha256") != EXPECTED_PHASE5_METADATA_SHA256:
        raise AblationContractError("Expanded metadata does not descend from Phase 5 metadata")
    if metadata.get("feature_columns") != EXPANDED_FEATURE_COLUMNS:
        raise AblationContractError("Expanded feature allowlist differs from its contract")
    frame = pd.read_csv(DATASET, low_memory=False)
    if len(frame) != metadata.get("rows") or frame.duplicated(
        ["ticker", "session_date"]
    ).any():
        raise AblationContractError("Expanded dataset row identity differs")
    required = {
        "ticker",
        "session_date",
        "target_window_end",
        "return_next_20d",
        "risk_volatility_next_20d",
        "relative_return_class",
        "risk_class",
        "return_eligible",
        "risk_eligible",
        *EXPANDED_FEATURE_COLUMNS,
    }
    if required - set(frame.columns):
        raise AblationContractError("Expanded dataset schema is incomplete")
    eligible = frame["return_eligible"] | frame["risk_eligible"]
    if frame.loc[eligible, ADDED_FEATURE_COLUMNS].isna().any().any():
        raise AblationContractError("Expansion changes eligible-row coverage")
    return frame, metadata


def build_expansion_protocol(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    phase5_protocol: dict[str, Any],
) -> dict[str, Any]:
    """Bind the unchanged Phase 5 folds to the expanded dataset identity."""

    if sha256(PHASE5_DATASET) != EXPECTED_PHASE5_DATASET_SHA256:
        raise AblationContractError("Phase 5 parent dataset identity changed")
    if sha256(PHASE5_METADATA) != EXPECTED_PHASE5_METADATA_SHA256:
        raise AblationContractError("Phase 5 parent metadata identity changed")
    if sha256(PHASE5_PROTOCOL) != EXPECTED_PHASE5_PROTOCOL_SHA256:
        raise AblationContractError("Phase 5 parent protocol identity changed")

    protocol = deepcopy(phase5_protocol)
    protocol["dataset_sha256"] = metadata["output_sha256"]
    protocol["feature_allowlist"] = EXPANDED_FEATURE_COLUMNS
    protocol["code_sha256"] = {
        "src/model_training/feature_ablation/phase6_market_expansion.py": sha256(
            __file__
        )
    }
    protocol["phase6_expansion"] = {
        "experiment_id": EXPERIMENT_ID,
        "parent_dataset_sha256": EXPECTED_PHASE5_DATASET_SHA256,
        "parent_protocol_sha256": EXPECTED_PHASE5_PROTOCOL_SHA256,
        "groups": EXPANSION_GROUPS,
        "comparison": (
            "Original 14 Phase 5 features versus the same matched rows with one "
            "predeclared three-feature group added."
        ),
    }
    protocol["experiment_protocol"] = deepcopy(protocol["experiment_protocol"])
    protocol["experiment_protocol"]["feature_groups"] = {
        **protocol["experiment_protocol"]["feature_groups"],
        **EXPANSION_GROUPS,
    }

    for fold in protocol["folds"]:
        for task in ("return", "risk"):
            for role in ("inner", "outer"):
                train, evaluation = fold_roles(frame, fold, task, role)
                if train[ADDED_FEATURE_COLUMNS].isna().any().any() or evaluation[
                    ADDED_FEATURE_COLUMNS
                ].isna().any().any():
                    raise AblationContractError(
                        f"Expansion has missing {task} values in fold {fold['fold']} {role}"
                    )
    return protocol


def prepare_expansion_inputs() -> dict[str, Any]:
    """Student-run dataset, protocol, and no-fit validation preparation."""

    # Reproduce only the immutable parent protocol when it is unavailable in a
    # fresh runtime. The old continuation preparation owns completed reports;
    # rerunning it after code changes could collide with that preserved evidence.
    if not PHASE5_PROTOCOL.exists():
        build_parent_protocol(PHASE5_DATASET, PHASE5_PROTOCOL)
    if sha256(PHASE5_PROTOCOL) != EXPECTED_PHASE5_PROTOCOL_SHA256:
        raise AblationContractError("Phase 5 parent protocol identity changed")
    if not DATASET.exists():
        build_expanded_dataset(PHASE5_DATASET, EXPANDED_DATASET_ROOT)
    frame, metadata = load_expanded_dataset()
    phase5_protocol = _load_json(PHASE5_PROTOCOL, "Phase 5 protocol")
    rebuilt = build_expansion_protocol(frame, metadata, phase5_protocol)
    if PROTOCOL.exists():
        saved = _load_json(PROTOCOL, "expansion protocol")
        if saved != rebuilt:
            raise FileExistsError("Existing expansion protocol differs; refusing overwrite")
    else:
        PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
        PROTOCOL.write_text(json.dumps(rebuilt, indent=2) + "\n", encoding="utf-8")

    validation = {
        "schema_version": 1,
        "stage": "phase_6_step_6_9_market_feature_expansion_validation",
        "status": "validated",
        "model_fitting_performed": False,
        "experiment_id": EXPERIMENT_ID,
        "input_identities": {
            "dataset": {"path": str(DATASET), "sha256": sha256(DATASET)},
            "metadata": {"path": str(METADATA), "sha256": sha256(METADATA)},
            "protocol": {"path": str(PROTOCOL), "sha256": sha256(PROTOCOL)},
            "parent_dataset_sha256": EXPECTED_PHASE5_DATASET_SHA256,
            "parent_protocol_sha256": EXPECTED_PHASE5_PROTOCOL_SHA256,
        },
        "groups": EXPANSION_GROUPS,
        "tasks": ["return", "risk"],
        "estimator": ESTIMATOR,
        "matched_rows_required": True,
        "selection_rule": (
            "Retain only with positive mean primary-metric difference and positive "
            "differences in at least three of four folds. Risk also requires "
            "non-worse High-risk recall and no increase in High-predicted-Low count."
        ),
    }
    if VALIDATION.exists():
        if _load_json(VALIDATION, "expansion validation") != validation:
            raise FileExistsError("Existing expansion validation differs")
    else:
        VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    return validation


def _select_features(
    train: pd.DataFrame,
    evaluation: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not columns or len(columns) != len(set(columns)):
        raise AblationContractError("Expansion feature selection is empty or duplicated")
    if set(columns) - set(EXPANDED_FEATURE_COLUMNS):
        raise AblationContractError("Expansion requested a non-allowlisted feature")
    assert_fold(train, evaluation, evaluation.session_date.min())
    x_train, x_evaluation = train[columns].copy(), evaluation[columns].copy()
    if x_train.isna().any().any() or x_evaluation.isna().any().any():
        raise AblationContractError("Expansion comparison contains missing values")
    return x_train, x_evaluation


def _run_variant(
    frame: pd.DataFrame,
    protocol: dict[str, Any],
    task: str,
    group_name: str,
    include_group: bool,
) -> dict[str, Any]:
    features = FEATURE_COLUMNS + (
        EXPANSION_GROUPS[group_name] if include_group else []
    )
    fold_results = []
    parameter_grid = _parameters(protocol, ESTIMATOR)
    for fold in protocol["folds"]:
        inner_train, inner_evaluation = fold_roles(frame, fold, task, "inner")
        outer_train, outer_evaluation = fold_roles(frame, fold, task, "outer")
        x_inner_train, x_inner_evaluation = _select_features(
            inner_train, inner_evaluation, features
        )
        y_inner_train, y_inner_evaluation, _ = _labels(
            inner_train, inner_evaluation, fold, task, role="inner"
        )
        selected, candidates = tune_on_inner_validation(
            task,
            ESTIMATOR,
            parameter_grid,
            x_inner_train,
            y_inner_train,
            x_inner_evaluation,
            y_inner_evaluation,
            inner_evaluation,
        )
        x_outer_train, x_outer_evaluation = _select_features(
            outer_train, outer_evaluation, features
        )
        y_outer_train, y_outer_evaluation, boundaries = _labels(
            outer_train, outer_evaluation, fold, task, role="outer"
        )
        probabilities = _fit_predict(
            ESTIMATOR,
            selected,
            x_outer_train,
            y_outer_train,
            x_outer_evaluation,
        )
        fold_results.append(
            {
                "fold": fold["fold"],
                "task": task,
                "estimator": ESTIMATOR,
                "variant": "with_group" if include_group else "without_group",
                "group": group_name,
                "features": features,
                "selected_parameters": selected,
                "inner_candidates": candidates,
                "inner_training_rows": len(inner_train),
                "inner_evaluation_rows": len(inner_evaluation),
                "outer_training_rows": len(outer_train),
                "outer_evaluation_rows": len(outer_evaluation),
                "inner_training_keys_sha256": _hash_keys(inner_train),
                "inner_evaluation_keys_sha256": _hash_keys(inner_evaluation),
                "outer_training_keys_sha256": _hash_keys(outer_train),
                "outer_evaluation_keys_sha256": _hash_keys(outer_evaluation),
                "outer_first": fold["outer_first"],
                "outer_last": fold["outer_last"],
                "risk_boundaries": boundaries,
                "metrics": _outer_metrics(
                    task,
                    outer_train,
                    outer_evaluation,
                    y_outer_train,
                    y_outer_evaluation,
                    probabilities,
                    boundaries,
                ),
            }
        )
    return {
        "schema_version": 1,
        "stage": "phase_6_step_6_9_market_feature_expansion",
        "status": "complete",
        "experiment_id": EXPERIMENT_ID,
        "task": task,
        "estimator": ESTIMATOR,
        "group": group_name,
        "variant": "with_group" if include_group else "without_group",
        "features": features,
        "dataset_sha256": sha256(DATASET),
        "protocol_sha256": sha256(PROTOCOL),
        "folds": fold_results,
    }


def write_group_comparison(group_name: str) -> dict[str, Any]:
    """Fit one new group once and write paired, new-only evidence."""

    if group_name not in EXPANSION_GROUPS:
        raise ValueError(f"Unknown expansion group: {group_name}")
    output_dir = (
        CROSS_SECTIONAL_OUTPUT
        if group_name == "cross_sectional_relative_strength"
        else MARKET_REGIME_OUTPUT
    )
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite expansion evidence: {output_dir}")
    prepare_expansion_inputs()
    frame, metadata = load_expanded_dataset()
    protocol = _load_json(PROTOCOL, "expansion protocol")
    phase5_protocol = _load_json(PHASE5_PROTOCOL, "Phase 5 protocol")
    if protocol != build_expansion_protocol(frame, metadata, phase5_protocol):
        raise AblationContractError("Expansion protocol does not reproduce")

    runs: dict[str, dict[str, Any]] = {}
    for task in ("return", "risk"):
        runs[f"{task}_with"] = _run_variant(
            frame, protocol, task, group_name, True
        )
        runs[f"{task}_without"] = _run_variant(
            frame, protocol, task, group_name, False
        )
    summaries = {
        task: _summarize_feature_group_comparison(
            task,
            runs[f"{task}_with"],
            runs[f"{task}_without"],
            group_name=group_name,
            comparison_description=(
                "The original 14 Phase 5 market features versus the same matched "
                f"rows with the {group_name} group added."
            ),
        )
        for task in ("return", "risk")
    }
    report = {
        "schema_version": 1,
        "stage": "phase_6_step_6_9_market_feature_expansion_summary",
        "status": "complete",
        "experiment_id": EXPERIMENT_ID,
        "group": group_name,
        "added_features": EXPANSION_GROUPS[group_name],
        "baseline_features": FEATURE_COLUMNS,
        "task_summaries": summaries,
        "input_identities": {
            "dataset_sha256": sha256(DATASET),
            "metadata_sha256": sha256(METADATA),
            "protocol_sha256": sha256(PROTOCOL),
            "parent_dataset_sha256": EXPECTED_PHASE5_DATASET_SHA256,
        },
        "limitations": [
            "This is development-fold feature evidence, not reserved-period, portfolio, or trading evidence.",
            "The fixed 50-stock research universe introduces survivorship and selection bias.",
            "SPY regime values have daily after-close availability; exact intraday source arrival is not proven.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in runs.items():
        (output_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    summary_path = output_dir / f"{group_name}_summary.json"
    summary_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def experiment_status() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "dataset_ready": DATASET.is_file(),
        "protocol_ready": PROTOCOL.is_file(),
        "validation_ready": VALIDATION.is_file(),
        "cross_sectional_complete": CROSS_SECTIONAL_OUTPUT.is_dir(),
        "market_regime_complete": MARKET_REGIME_OUTPUT.is_dir(),
    }
