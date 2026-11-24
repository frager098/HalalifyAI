"""Validate the frozen Phase 8 contract without reading reserved outcomes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.model_training.chronological_evaluation_protocol import _hash_keys


DEFAULT_CONTRACT = Path("configs/phase8_evaluation_contract_v1.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("status") != "frozen_before_phase_8_feature_label_generation_or_scoring":
        raise ValueError("Phase 8 contract is not frozen at the required stage")
    if contract.get("outcomes_inspected") or contract.get("model_fitting_performed"):
        raise ValueError("Phase 8 contract claims outcomes or fitting already occurred")
    return contract


def _verify_identity(root: Path, identity: dict[str, str]) -> None:
    path = root / identity["path"]
    if not path.is_file() or sha256(path) != identity["sha256"]:
        raise ValueError(f"Phase 8 input identity mismatch: {identity['path']}")


def validate_contract(
    contract_path: Path = DEFAULT_CONTRACT, root: Path = Path(".")
) -> dict[str, Any]:
    root = root.resolve()
    contract_path = (root / contract_path).resolve() if not contract_path.is_absolute() else contract_path
    contract = load_contract(contract_path)
    for identity in contract["input_identities"].values():
        _verify_identity(root, identity)
    for identity in contract["feature_contract"].values():
        if isinstance(identity, dict) and {"path", "sha256"}.issubset(identity):
            _verify_identity(root, identity)
    _verify_identity(root, contract["label_contract"]["reference_code"])

    accepted = json.loads(
        (root / contract["input_identities"]["accepted_snapshot"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    report = json.loads(
        (root / contract["input_identities"]["cleaning_acceptance_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if accepted.get("outcomes_inspected") or accepted.get("labels_created"):
        raise ValueError("Accepted snapshot is not outcome-blind")
    if not report.get("accepted") or report.get("outcomes_inspected") or report.get("labels_created"):
        raise ValueError("Phase 8 cleaning acceptance is invalid")

    freeze = json.loads(
        (root / contract["input_identities"]["phase7_model_freeze"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if freeze["return"] != {"kind": "simple_benchmark", "benchmark": "momentum_20d"}:
        raise ValueError("Return selection differs from Phase 7")
    if freeze["risk"] != {
        "kind": "simple_benchmark",
        "benchmark": "volatility_20d_with_fold_training_cutoffs",
    }:
        raise ValueError("Risk selection differs from Phase 7")

    data_path = root / contract["input_identities"]["development_dataset"]["path"]
    required = [
        "ticker",
        "session_date",
        "target_window_end",
        "risk_volatility_next_20d",
        *FEATURE_COLUMNS,
    ]
    frame = pd.read_csv(data_path, usecols=required, low_memory=False)
    start = contract["chronology"]["reserved_evaluation_start"]
    mask = (
        frame["session_date"].lt(start)
        & frame["target_window_end"].notna()
        & frame["target_window_end"].lt(start)
        & frame["risk_volatility_next_20d"].notna()
        & frame[FEATURE_COLUMNS].notna().all(axis=1)
    )
    training = frame.loc[mask].copy()
    saved = contract["training_role"]
    if len(training) != saved["rows"] or _hash_keys(training) != saved["ticker_date_keys_sha256"]:
        raise ValueError("Frozen Phase 8 training role differs")
    if training["session_date"].max() != saved["last_decision_date"]:
        raise ValueError("Last training decision date differs")
    if training["target_window_end"].max() != saved["last_target_window_end"]:
        raise ValueError("Training target crosses the reserved period")

    cutoffs = training["risk_volatility_next_20d"].quantile([1 / 3, 2 / 3]).to_numpy()
    risk = contract["label_contract"]["risk_classes"]
    if not np.allclose(
        cutoffs,
        [risk["low_upper_inclusive"], risk["medium_upper_inclusive"]],
        rtol=0,
        atol=1e-15,
    ):
        raise ValueError("Frozen final risk cutoffs differ")
    classes = np.select(
        [
            training["risk_volatility_next_20d"].le(cutoffs[0]),
            training["risk_volatility_next_20d"].le(cutoffs[1]),
        ],
        [0, 1],
        default=2,
    )
    counts = np.bincount(classes, minlength=3).tolist()
    if counts != risk["training_class_counts"]:
        raise ValueError("Frozen risk class counts differ")

    chronology = contract["chronology"]
    if not (
        chronology["last_training_target_window_end"]
        < chronology["reserved_evaluation_start"]
        <= chronology["reserved_evaluation_end"]
        < chronology["twentieth_support_session"]
    ):
        raise ValueError("Phase 8 chronology is invalid")
    if contract["feature_contract"]["base_features"] != FEATURE_COLUMNS:
        raise ValueError("Base feature order differs from frozen implementation")

    return {
        "stage": "phase_8_step_8_2_contract_validation",
        "passed": True,
        "outcomes_inspected": False,
        "model_fitting_performed": False,
        "contract_sha256": sha256(contract_path),
        "training_rows": len(training),
        "training_keys_sha256": _hash_keys(training),
        "risk_cutoffs": [float(cutoffs[0]), float(cutoffs[1])],
        "phase7_selections_reproduced": True,
    }
