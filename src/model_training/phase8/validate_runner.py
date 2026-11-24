"""Validate the final Phase 8 runner without reading reserved outcome values.

Student-run command:
    python -m src.model_training.phase8.validate_runner
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import exchange_calendars as xc
import numpy as np
import pandas as pd

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.model_training.phase8.build_reserved_dataset import sha256
from src.model_training.phase8.contract import DEFAULT_CONTRACT, validate_contract
from src.model_training.phase8.runner import (
    evaluate_reserved_once,
    return_benchmark_metrics,
    risk_benchmark_metrics,
)


DEFAULT_DATASET_DIR = Path(
    "data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1"
)
DEFAULT_OUTPUT = Path(
    "reports/model_evaluation/phase8_reserved_evaluation_v1/runner_validation.json"
)
SAFE_AUDIT_COLUMNS = [
    "ticker",
    "session_date",
    "target_window_end",
    "return_eligible",
    "risk_eligible",
    "active_peer_count",
    *FEATURE_COLUMNS,
]
RESERVED_OUTCOME_COLUMNS = {
    "return_next_20d",
    "risk_volatility_next_20d",
    "relative_return_class",
    "risk_class",
}


def audit_real_inputs_without_outcomes(
    *, root: Path, contract_path: Path, dataset_dir: Path
) -> dict[str, Any]:
    """Audit real chronology/schema while never loading reserved outcome values."""
    root = root.resolve()
    contract_path = (
        (root / contract_path).resolve() if not contract_path.is_absolute() else contract_path
    )
    dataset_dir = (
        (root / dataset_dir).resolve() if not dataset_dir.is_absolute() else dataset_dir
    )
    contract_validation = validate_contract(contract_path, root)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    metadata_path = dataset_dir / "dataset_metadata.json"
    validation_path = dataset_dir / "validation_report.json"
    dataset_path = dataset_dir / "reserved_features_and_labels.csv"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    dataset_validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not dataset_validation.get("passed") or dataset_validation.get("outcomes_scored"):
        raise ValueError("Step 8.3 dataset validation did not pass unscored")
    if metadata["contract_sha256"] != contract_validation["contract_sha256"]:
        raise ValueError("Step 8.3 contract identity differs")
    if sha256(dataset_path) != metadata["output_sha256"]:
        raise ValueError("Step 8.3 dataset checksum mismatch")
    if metadata["feature_columns"] != FEATURE_COLUMNS:
        raise ValueError("Step 8.3 feature order differs")
    if metadata["scoring_allowlist"] != contract["feature_contract"]["scoring_allowlist"]:
        raise ValueError("Step 8.3 scoring allowlist differs")
    expected_cutoffs = [
        contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
        contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
    ]
    if metadata["risk_cutoffs"] != expected_cutoffs:
        raise ValueError("Step 8.3 risk cutoffs differ")

    header = pd.read_csv(dataset_path, nrows=0).columns.tolist()
    required = set(SAFE_AUDIT_COLUMNS) | RESERVED_OUTCOME_COLUMNS
    if required - set(header):
        raise ValueError(f"Reserved schema is missing {sorted(required - set(header))}")
    if set(SAFE_AUDIT_COLUMNS) & RESERVED_OUTCOME_COLUMNS:
        raise RuntimeError("Safe audit columns accidentally include outcomes")
    safe = pd.read_csv(dataset_path, usecols=SAFE_AUDIT_COLUMNS, low_memory=False)
    if len(safe) != 9350 or safe.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Reserved key count or uniqueness differs")
    if safe[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Reserved feature matrix contains missing values")
    if not safe["return_eligible"].eq(True).all() or not safe["risk_eligible"].eq(True).all():
        raise ValueError("Reserved eligibility differs")

    chronology = contract["chronology"]
    calendar = xc.get_calendar(
        "XNYS",
        start=pd.Timestamp(chronology["reserved_evaluation_start"]) - pd.Timedelta(days=10),
        end=pd.Timestamp(chronology["twentieth_support_session"]) + pd.Timedelta(days=10),
    )
    sessions = calendar.sessions_in_range(
        chronology["reserved_evaluation_start"], chronology["twentieth_support_session"]
    ).tz_localize(None)
    expected_end = pd.Series(sessions, index=sessions).shift(-20)
    dates = pd.to_datetime(safe["session_date"], format="%Y-%m-%d")
    observed_end = pd.to_datetime(safe["target_window_end"], format="%Y-%m-%d")
    if not observed_end.eq(dates.map(expected_end)).all():
        raise ValueError("Reserved target-window chronology differs")
    if safe["session_date"].min() != chronology["reserved_evaluation_start"]:
        raise ValueError("Reserved evaluation start differs")
    if safe["session_date"].max() != chronology["reserved_evaluation_end"]:
        raise ValueError("Reserved evaluation end differs")
    if safe["target_window_end"].max() != chronology["twentieth_support_session"]:
        raise ValueError("Reserved support end differs")
    if safe["active_peer_count"].min() < 45:
        raise ValueError("Reserved active-peer quorum differs")

    development_path = root / contract["input_identities"]["development_dataset"]["path"]
    training_keys = pd.read_csv(
        development_path,
        usecols=["ticker", "session_date", "target_window_end"],
        low_memory=False,
    )
    training_keys = training_keys.loc[
        training_keys["target_window_end"].notna()
        & training_keys["target_window_end"].lt(chronology["reserved_evaluation_start"])
    ]
    if training_keys["target_window_end"].max() >= safe["session_date"].min():
        raise ValueError("Training outcome overlaps reserved evaluation")
    training_key_set = set(zip(training_keys["ticker"], training_keys["session_date"]))
    reserved_key_set = set(zip(safe["ticker"], safe["session_date"]))
    if training_key_set & reserved_key_set:
        raise ValueError("Training and reserved keys overlap")

    return {
        "schema_valid": True,
        "feature_allowlist_valid": True,
        "scoring_allowlist_valid": True,
        "training_reserved_separation_valid": True,
        "target_window_purge_valid": True,
        "training_only_cutoffs_valid": True,
        "reserved_rows": len(safe),
        "reserved_sessions": int(safe["session_date"].nunique()),
        "minimum_active_companies": int(safe["active_peer_count"].min()),
        "dataset_sha256": metadata["output_sha256"],
        "contract_sha256": contract_validation["contract_sha256"],
        "reserved_outcome_values_read": False,
    }


def synthetic_runner_checks(contract: dict[str, Any]) -> dict[str, Any]:
    """Exercise runner metrics on synthetic values, never reserved outcomes."""
    return_rows = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"] * 2,
            "session_date": ["2020-01-02"] * 3 + ["2020-01-03"] * 3,
            "return_next_20d": [0.01, 0.02, 0.03, -0.01, 0.00, 0.01],
            "momentum_20d": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        }
    )
    first_return = return_benchmark_metrics(return_rows)
    second_return = return_benchmark_metrics(return_rows.copy())
    if first_return != second_return or first_return["mean_daily_spearman"] != 1.0:
        raise ValueError("Return runner is not deterministic")

    cutoffs = [
        contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
        contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
    ]
    risk_values = [cutoffs[0] / 2, sum(cutoffs) / 2, cutoffs[1] * 1.5]
    risk_rows = pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "session_date": ["2020-01-02"] * 3,
            "risk_volatility_next_20d": risk_values,
            "risk_class": [0, 1, 2],
            "volatility_20d": risk_values,
        }
    )
    first_risk = risk_benchmark_metrics(risk_rows, cutoffs)
    second_risk = risk_benchmark_metrics(risk_rows.copy(), cutoffs)
    if first_risk != second_risk or first_risk["macro_f1"] != 1.0:
        raise ValueError("Risk runner is not deterministic")
    return {
        "synthetic_return_runner_deterministic": True,
        "synthetic_risk_runner_deterministic": True,
        "hard_class_probability_metrics_omitted": True,
    }


def validate_runner(
    *,
    root: Path,
    contract_path: Path,
    dataset_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output_path = (
        (root / output_path).resolve() if not output_path.is_absolute() else output_path
    )
    if output_path.exists():
        raise FileExistsError(output_path)
    contract_path = (
        (root / contract_path).resolve() if not contract_path.is_absolute() else contract_path
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    audit = audit_real_inputs_without_outcomes(
        root=root, contract_path=contract_path, dataset_dir=dataset_dir
    )
    synthetic = synthetic_runner_checks(contract)
    result = {
        "stage": "phase_8_step_8_4_runner_validation",
        "status": "passed",
        "model_fitting_performed": False,
        "reserved_outcome_values_read": False,
        "performance_metrics_calculated_on_reserved_period": False,
        "evaluation_output_created": False,
        "audit": audit,
        "synthetic_checks": synthetic,
        "overwrite_refusal": True,
        "runner_code_sha256": sha256(root / "src/model_training/phase8/runner.py"),
        "validator_code_sha256": sha256(Path(__file__)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, type=Path)
    parser.add_argument("--dataset-dir", default=DEFAULT_DATASET_DIR, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()
    result = validate_runner(
        root=args.root,
        contract_path=args.contract,
        dataset_dir=args.dataset_dir,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
