"""One-time Phase 8 reserved-period evaluation entry point.

This module is called by ``notebooks/phase8_one_time_evaluation.ipynb``. It
refuses to overwrite a prior result and checks that destination before reading
the reserved dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.model_training.phase8.build_reserved_dataset import sha256
from src.model_training.phase8.procedure import (
    DEFAULT_PROCEDURE,
    validate_runtime_gate,
)
from src.model_training.phase8.runner import (
    return_benchmark_metrics,
    risk_benchmark_metrics,
)


DEFAULT_DATASET_DIR = Path(
    "data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1"
)
DEFAULT_OUTPUT = Path(
    "reports/model_evaluation/phase8_reserved_evaluation_v1/one_time_evaluation.json"
)


def numeric_distribution(values: pd.Series) -> dict[str, float | int]:
    numeric = pd.to_numeric(values, errors="raise")
    if numeric.empty or numeric.isna().any() or not np.isfinite(numeric).all():
        raise ValueError("Distribution input is empty, missing, or non-finite")
    return {
        "count": int(len(numeric)),
        "mean": float(numeric.mean()),
        "sample_std": float(numeric.std(ddof=1)),
        "minimum": float(numeric.min()),
        "q25": float(numeric.quantile(0.25)),
        "median": float(numeric.median()),
        "q75": float(numeric.quantile(0.75)),
        "maximum": float(numeric.max()),
    }


def class_counts(values: pd.Series) -> list[int]:
    numeric = pd.to_numeric(values, errors="raise").astype(int).to_numpy()
    if not np.isin(numeric, [0, 1, 2]).all():
        raise ValueError("Unexpected class code")
    return np.bincount(numeric, minlength=3).tolist()


def run_one_time_evaluation(
    *,
    root: Path = Path("."),
    procedure_path: Path = DEFAULT_PROCEDURE,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    root = root.resolve()
    procedure_path = (
        (root / procedure_path).resolve() if not procedure_path.is_absolute() else procedure_path
    )
    dataset_dir = (
        (root / dataset_dir).resolve() if not dataset_dir.is_absolute() else dataset_dir
    )
    output_path = (
        (root / output_path).resolve() if not output_path.is_absolute() else output_path
    )
    # Refuse before reading the reserved dataset so a second run cannot inspect
    # outcomes and then fail only at write time.
    if output_path.exists():
        raise FileExistsError(output_path)

    gate = validate_runtime_gate(procedure_path, root)
    freeze = json.loads(procedure_path.read_text(encoding="utf-8"))
    metadata_path = dataset_dir / "dataset_metadata.json"
    validation_path = dataset_dir / "validation_report.json"
    dataset_path = dataset_dir / "reserved_features_and_labels.csv"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    dataset_validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not dataset_validation.get("passed") or dataset_validation.get("outcomes_scored"):
        raise ValueError("Reserved dataset is not validated and unscored")
    if sha256(dataset_path) != gate["dataset_sha256"]:
        raise ValueError("Reserved dataset differs from the Step 8.5 freeze")
    if metadata.get("output_sha256") != gate["dataset_sha256"]:
        raise ValueError("Reserved dataset metadata identity differs")
    if metadata.get("performance_metrics_calculated") or metadata.get("outcomes_scored"):
        raise ValueError("Reserved metadata claims prior scoring")

    rows = pd.read_csv(dataset_path, low_memory=False)
    if len(rows) != 9350 or rows.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Reserved evaluation row identity differs")
    return_rows = rows.loc[rows["return_eligible"].eq(True)].copy()
    risk_rows = rows.loc[rows["risk_eligible"].eq(True)].copy()
    if len(return_rows) != 9350 or len(risk_rows) != 9350:
        raise ValueError("Reserved evaluation eligibility differs")

    return_result = return_benchmark_metrics(return_rows)
    return_result["future_return_distribution"] = numeric_distribution(
        return_rows["return_next_20d"]
    )
    return_result["relative_class_counts"] = class_counts(
        return_rows["relative_return_class"]
    )
    risk_result = risk_benchmark_metrics(risk_rows, gate["risk_cutoffs"])

    result = {
        "schema_version": 1,
        "stage": "phase_8_step_8_6_one_time_reserved_evaluation",
        "status": "complete",
        "one_time_evaluation": True,
        "model_fitting_performed": False,
        "selection_reopened": False,
        "procedure_freeze_sha256": gate["procedure_freeze_sha256"],
        "contract_sha256": gate["contract_sha256"],
        "dataset_sha256": gate["dataset_sha256"],
        "runner_validation_sha256": gate["runner_validation_sha256"],
        "runner_code_sha256": gate["runner_code_sha256"],
        "evaluation_code_sha256": sha256(Path(__file__)),
        "evaluation_period": {
            "first_session": rows["session_date"].min(),
            "last_session": rows["session_date"].max(),
            "sessions": int(rows["session_date"].nunique()),
            "companies": int(rows["ticker"].nunique()),
        },
        "eligibility": {
            "total_rows": int(len(rows)),
            "return_eligible_rows": int(len(return_rows)),
            "risk_eligible_rows": int(len(risk_rows)),
            "return_excluded_rows": int(len(rows) - len(return_rows)),
            "risk_excluded_rows": int(len(rows) - len(risk_rows)),
            "return_reasons": {
                str(key): int(value)
                for key, value in rows["return_eligibility_reason"].value_counts().items()
            },
            "risk_reasons": {
                str(key): int(value)
                for key, value in rows["risk_eligibility_reason"].value_counts().items()
            },
        },
        "return": return_result,
        "risk": risk_result,
        "limitations": metadata["limitations"],
        "interpretation_guardrails": [
            "This is a one-time reserved-period research evaluation.",
            "No result may trigger tuning while retaining the same test claim.",
            "This is not portfolio, trading, whole-market, or Shariah-compliance evidence."
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    return result
