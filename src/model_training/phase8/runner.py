"""Frozen Phase 8 benchmark runner.

The real reserved-period evaluation is intentionally not exposed as a default
command. Step 8.4 validates this module with synthetic outcomes and audits the
real reserved dataset without reading its outcome values. A later one-time
entry point may call ``evaluate_reserved_once`` only after that gate passes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
)

from src.model_training.baseline_models import _return_ranking
from src.model_training.chronological_evaluation_protocol import apply_risk_boundaries
from src.model_training.phase8.build_reserved_dataset import sha256


CLASS_ORDER = [0, 1, 2]


def return_benchmark_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    """Score frozen momentum ranking; no fitting or probability is involved."""
    required = {"ticker", "session_date", "return_next_20d", "momentum_20d"}
    if required - set(rows.columns):
        raise ValueError(f"Missing return runner columns: {sorted(required - set(rows.columns))}")
    if rows.empty or rows[list(required)].isna().any().any():
        raise ValueError("Return runner received empty or missing values")
    ranking = _return_ranking(rows, rows["momentum_20d"])
    return {
        "procedure": "momentum_20d",
        "primary_metric": "mean_daily_spearman",
        "mean_daily_spearman": ranking["mean_daily_spearman"],
        "mean_top10_minus_universe_return": ranking["mean_top10_minus_universe"],
        "evaluation_dates": ranking["dates"],
        "defined_spearman_dates": ranking["defined_spearman_dates"],
        "daily": ranking["daily"],
    }


def risk_benchmark_metrics(
    rows: pd.DataFrame, cutoffs: list[float]
) -> dict[str, Any]:
    """Score frozen trailing volatility classes against future-risk classes."""
    required = {
        "ticker",
        "session_date",
        "risk_volatility_next_20d",
        "risk_class",
        "volatility_20d",
    }
    if required - set(rows.columns):
        raise ValueError(f"Missing risk runner columns: {sorted(required - set(rows.columns))}")
    if rows.empty or rows[list(required)].isna().any().any():
        raise ValueError("Risk runner received empty or missing values")
    truth = rows["risk_class"].astype(int).to_numpy()
    reconstructed = apply_risk_boundaries(rows["risk_volatility_next_20d"], cutoffs)
    if not np.array_equal(truth, reconstructed):
        raise ValueError("Saved risk classes differ from the frozen cutoffs")
    prediction = apply_risk_boundaries(rows["volatility_20d"], cutoffs)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, prediction, labels=CLASS_ORDER, zero_division=0
    )
    high_outcomes = int((truth == 2).sum())
    high_to_low = int(((truth == 2) & (prediction == 0)).sum())
    names = ["Low", "Medium", "High"]
    return {
        "procedure": "volatility_20d_with_training_cutoffs",
        "primary_metric": "macro_f1",
        "macro_f1": float(
            f1_score(truth, prediction, labels=CLASS_ORDER, average="macro", zero_division=0)
        ),
        "per_class": {
            name: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, name in enumerate(names)
        },
        "high_recall": float(
            recall_score(truth, prediction, labels=[2], average="macro", zero_division=0)
        ),
        "high_outcomes": high_outcomes,
        "high_to_low_count": high_to_low,
        "high_to_low_rate": float(high_to_low / high_outcomes) if high_outcomes else None,
        "ordinal_mae": float(np.mean(np.abs(truth - prediction))),
        "confusion_matrix": confusion_matrix(truth, prediction, labels=CLASS_ORDER).tolist(),
        "true_class_counts": np.bincount(truth, minlength=3).tolist(),
        "predicted_class_counts": np.bincount(prediction, minlength=3).tolist(),
        "probability_metrics": "not_applicable_no_probabilities",
    }


def evaluate_reserved_once(
    *,
    dataset_path: Path,
    metadata_path: Path,
    contract: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    """Run the frozen one-time evaluation and refuse an existing destination."""
    if output_path.exists():
        raise FileExistsError(output_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if sha256(dataset_path) != metadata["output_sha256"]:
        raise ValueError("Reserved dataset checksum mismatch")
    if metadata.get("outcomes_scored") or metadata.get("performance_metrics_calculated"):
        raise ValueError("Reserved metadata already claims evaluation occurred")
    rows = pd.read_csv(dataset_path, low_memory=False)
    return_rows = rows.loc[rows["return_eligible"].eq(True)].copy()
    risk_rows = rows.loc[rows["risk_eligible"].eq(True)].copy()
    cutoffs = [
        contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
        contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
    ]
    result = {
        "stage": "phase_8_one_time_reserved_evaluation",
        "status": "complete",
        "model_fitting_performed": False,
        "selection_reopened": False,
        "contract_sha256": metadata["contract_sha256"],
        "dataset_sha256": metadata["output_sha256"],
        "return": return_benchmark_metrics(return_rows),
        "risk": risk_benchmark_metrics(risk_rows, cutoffs),
        "limitations": metadata["limitations"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    return result
