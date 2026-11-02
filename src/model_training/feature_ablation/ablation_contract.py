"""Freeze and verify the Phase 6 feature-ablation contract.

This module contains reusable validation logic for the student-run
``notebooks/feature_ablation_report.ipynb`` notebook. It does not fit a model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

# VS Code's Run Python File button executes this file by path, so Python adds
# src/model_training rather than the repository root to sys.path. Keep normal
# package imports while making that beginner-friendly direct-run path work.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.baseline_models import verify_inputs


DEFAULT_DATASET = Path(
    "data/processed/model_inputs/market_features_and_labels_v1/"
    "market_features_and_labels.csv"
)
DEFAULT_METADATA = DEFAULT_DATASET.with_name("dataset_metadata.json")
DEFAULT_PROTOCOL = Path(
    "reports/model_evaluation/baseline_comparison/v1/refactored_evidence/"
    "chronological_evaluation_protocol.json"
)
DEFAULT_BASELINES = DEFAULT_PROTOCOL.with_name("baseline_model_results.json")
DEFAULT_RETURN_COMPARISON = DEFAULT_PROTOCOL.with_name("return_model_comparison.json")
DEFAULT_RISK_COMPARISON = DEFAULT_PROTOCOL.with_name("risk_model_comparison.json")
DEFAULT_OUTPUT = Path(
    "reports/model_evaluation/feature_ablation/v1/ablation_contract.json"
)

FROZEN_HASHES = {
    "dataset": "71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f",
    "metadata": "b36ed46ac5a68b74130b26df8f20d965928c53d62467c163a214f8b37fd35ba9",
    "protocol": "048d82ce2ed0bedde60bd5f6215303fa86ebdab31aae5b5c330f0947372859ff",
    "baselines": "0e5f1fc1798844ec793d2bfbc98ade2683609134e40a05e30f0a0f83ff8f5438",
    "return_comparison": "62060fe17b7ab74ef6b4e4461d8da3ae7d4188d811cd2da46aeeee8c525419b9",
    "risk_comparison": "4866ccd580bd64121b9eb0ae779e7b818e54ad317e2804dea0b9737daef75943",
}

EXPECTED_FEATURE_ALLOWLIST = [
    "return_1d",
    "momentum_5d",
    "momentum_20d",
    "momentum_60d",
    "volatility_20d",
    "volatility_60d",
    "downside_dev_20d",
    "drawdown_from_peak_60d",
    "price_to_sma20",
    "price_to_sma50",
    "volume_ratio_20d",
    "spy_momentum_20d",
    "excess_momentum_20d",
    "market_beta_60d",
]

EXPECTED_FOLD_DATES = [
    {"fold": 1, "inner_first": "2019-12-26", "inner_last": "2020-06-25",
     "outer_first": "2020-06-26", "outer_last": "2021-06-25"},
    {"fold": 2, "inner_first": "2020-12-24", "inner_last": "2021-06-25",
     "outer_first": "2021-06-28", "outer_last": "2022-06-27"},
    {"fold": 3, "inner_first": "2021-12-27", "inner_last": "2022-06-27",
     "outer_first": "2022-06-28", "outer_last": "2023-06-28"},
    {"fold": 4, "inner_first": "2022-12-27", "inner_last": "2023-06-28",
     "outer_first": "2023-06-29", "outer_last": "2024-06-28"},
]

EXPECTED_BENCHMARKS = [
    "training_class_prior",
    "momentum_20d_rank",
    "trailing_volatility_20d_with_fold_risk_cutoffs",
    "preserved_Ridge_numerical_forecasts",
    "preserved_SPY_relative_results",
]

RETURN_CONCLUSION = (
    "Select no return approach. Keep trailing 20-day momentum only as a simple "
    "benchmark/control; its mean outer Spearman is effectively zero and it is "
    "not an endorsed effective strategy."
)

RESEARCH_QUESTIONS = {
    "return": {
        "question": (
            "On identical eligible outer-fold ticker-date rows, does the "
            "predeclared feature group improve mean within-date Spearman return "
            "ordering over its matched feature-excluded reference and the "
            "20-day momentum control?"
        ),
        "primary_metric": "equal-weight mean of outer-fold mean within-date Spearman",
        "baseline": "momentum_20d_rank",
        "guardrails": [
            "keep the Phase 4 folds, eligible rows, labels, model, and tuning budget fixed",
            "report all four folds and matched-row coverage",
            "do not promote a group from one fold or from the reused 2024-2025 period",
        ],
    },
    "risk": {
        "question": (
            "On identical eligible outer-fold ticker-date rows, does the "
            "predeclared feature group improve risk-class macro F1 over its "
            "matched feature-excluded reference and the fold-cutoff trailing "
            "20-day volatility baseline without hiding worse High-risk recall "
            "or High-to-Low errors?"
        ),
        "primary_metric": "equal-weight mean outer-fold macro F1",
        "baseline": "trailing_volatility_20d_with_fold_risk_cutoffs",
        "guardrails": [
            "use only the already frozen fold-specific training cutoffs",
            "report all four folds, High recall, High-to-Low errors, and matched-row coverage",
            "do not treat the risk research candidate as approved for user-facing decisions",
        ],
    },
}


class ContractMismatchError(ValueError):
    """Raised when Phase 6 inputs differ from the frozen contract."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ContractMismatchError(f"Missing frozen {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractMismatchError(f"Cannot read frozen {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ContractMismatchError(f"Frozen {label} must contain a JSON object")
    return value


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ContractMismatchError(
            f"{label} mismatch; expected {expected!r}, received {actual!r}"
        )


def _verify_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise ContractMismatchError(f"Missing frozen {label}: {path}")
    actual = sha256(path)
    _require_equal(actual, expected, f"{label} SHA-256")
    return actual


def _fold_summary(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for fold in protocol["folds"]:
        item = {
            key: fold[key]
            for key in ("fold", "inner_first", "inner_last", "outer_first", "outer_last")
        }
        item["tasks"] = {}
        for task in ("return", "risk"):
            outer = fold["tasks"][task]["outer"]
            item["tasks"][task] = {
                "train_rows": outer["train_rows"],
                "evaluation_rows": outer["evaluation_rows"],
                "train_keys_sha256": outer["train_keys_sha256"],
                "evaluation_keys_sha256": outer["evaluation_keys_sha256"],
            }
        item["tasks"]["risk"]["training_boundaries"] = fold["tasks"]["risk"][
            "outer"
        ]["risk_boundaries"]
        summary.append(item)
    return summary


def build_ablation_contract_report(
    dataset_path: Path = DEFAULT_DATASET,
    metadata_path: Path = DEFAULT_METADATA,
    protocol_path: Path = DEFAULT_PROTOCOL,
    baselines_path: Path = DEFAULT_BASELINES,
    return_comparison_path: Path = DEFAULT_RETURN_COMPARISON,
    risk_comparison_path: Path = DEFAULT_RISK_COMPARISON,
) -> dict[str, Any]:
    """Verify every frozen input and return the Phase 6.1 report."""

    paths = {
        "dataset": Path(dataset_path),
        "metadata": Path(metadata_path),
        "protocol": Path(protocol_path),
        "baselines": Path(baselines_path),
        "return_comparison": Path(return_comparison_path),
        "risk_comparison": Path(risk_comparison_path),
    }
    expected_metadata_path = paths["dataset"].with_name("dataset_metadata.json")
    if paths["metadata"].resolve() != expected_metadata_path.resolve():
        raise ContractMismatchError(
            "Metadata must be the dataset_metadata.json beside the frozen dataset"
        )
    actual_hashes = {
        name: _verify_hash(paths[name], FROZEN_HASHES[name], name)
        for name in paths
    }

    # Reconstructing Phase 4 validates eligibility, purges, row-key hashes,
    # fold risk cutoffs, ranking groups, complete features, and the allowlist.
    _, metadata, protocol = verify_inputs(paths["dataset"], paths["protocol"])
    baselines = _load_json(paths["baselines"], "Phase 5 baseline report")
    return_comparison = _load_json(
        paths["return_comparison"], "Phase 5 return comparison"
    )
    risk_comparison = _load_json(paths["risk_comparison"], "Phase 5 risk comparison")

    _require_equal(protocol["feature_allowlist"], EXPECTED_FEATURE_ALLOWLIST, "feature allowlist")
    observed_dates = [
        {
            key: fold[key]
            for key in ("fold", "inner_first", "inner_last", "outer_first", "outer_last")
        }
        for fold in protocol["folds"]
    ]
    _require_equal(observed_dates, EXPECTED_FOLD_DATES, "four development folds")
    _require_equal(
        protocol["experiment_protocol"]["benchmarks"],
        EXPECTED_BENCHMARKS,
        "Phase 5 benchmark list",
    )
    _require_equal(baselines["dataset_sha256"], FROZEN_HASHES["dataset"], "baseline dataset")
    _require_equal(baselines["protocol_sha256"], FROZEN_HASHES["protocol"], "baseline protocol")
    _require_equal(baselines["feature_allowlist"], EXPECTED_FEATURE_ALLOWLIST, "baseline allowlist")
    _require_equal(len(baselines["folds"]), 16, "baseline task/role result count")

    for label, comparison in (
        ("return comparison", return_comparison),
        ("risk comparison", risk_comparison),
    ):
        _require_equal(comparison["dataset_sha256"], FROZEN_HASHES["dataset"], f"{label} dataset")
        _require_equal(comparison["protocol_sha256"], FROZEN_HASHES["protocol"], f"{label} protocol")
    _require_equal(return_comparison["decision"], RETURN_CONCLUSION, "Phase 5 return conclusion")

    risk_summary = risk_comparison["summary"]
    expected_risk_methods = {
        "LogisticRegression",
        "HistGradientBoosting",
        "training_class_prior",
        "trailing_volatility_20d",
    }
    _require_equal(set(risk_summary), expected_risk_methods, "Phase 5 risk methods")
    if not (
        risk_summary["HistGradientBoosting"]["mean_fold_macro_f1"]
        > risk_summary["trailing_volatility_20d"]["mean_fold_macro_f1"]
    ):
        raise ContractMismatchError("Phase 5 risk-candidate conclusion no longer holds")

    return {
        "schema_version": 1,
        "stage": "phase_6_step_6_1_ablation_contract",
        "status": "verified",
        "input_identities": {
            name: {"path": str(paths[name]), "sha256": actual_hashes[name]}
            for name in paths
        },
        "dataset": {
            "rows": metadata["rows"],
            "companies": metadata["companies"],
            "eligible_rows": metadata["eligible_counts"],
            "eligibility_rule": (
                "Use return_eligible or risk_eligible for the named task; "
                "the reconstructed Phase 4 role keys must match exactly."
            ),
            "reused_test_start": metadata["reused_test_start"],
            "reused_test_status": protocol["reused_test_status"],
        },
        "feature_allowlist": protocol["feature_allowlist"],
        "development_folds": _fold_summary(protocol),
        "baselines": {
            "all_frozen_protocol_entries": EXPECTED_BENCHMARKS,
            "return_primary_control": "momentum_20d_rank",
            "risk_primary_baseline": "trailing_volatility_20d_with_fold_risk_cutoffs",
            "training_class_prior": "weak no-fit reference for both tasks",
            "preserved_results": (
                "Ridge numerical forecasts and SPY-relative results are prior "
                "benchmarks unless rerun on the matched Phase 4 rows."
            ),
        },
        "phase_5_conclusions": {
            "return": RETURN_CONCLUSION,
            "return_mean_fold_spearman": return_comparison["mean_fold_spearman"],
            "risk": (
                "HistGradientBoosting is a research candidate, not an approved "
                "user-facing model. Its macro-F1 gain must remain beside High "
                "recall and High-to-Low errors."
            ),
            "risk_summary": risk_summary,
        },
        "research_questions": RESEARCH_QUESTIONS,
        "comparison_rule": (
            "For each task and feature group, preserve the Phase 4 folds, "
            "Phase 5 model/tuning budget, task eligibility, labels, and outer "
            "row keys. Fit preprocessing and tune only on training-side rows."
        ),
        "stop_rule": (
            "Any identity, hash, fold, eligibility, allowlist, baseline, or "
            "Phase 5 conclusion mismatch raises ContractMismatchError before "
            "an ablation report is returned or written."
        ),
    }


def write_ablation_contract_report(
    output_path: Path = DEFAULT_OUTPUT, **paths: Path
) -> dict[str, Any]:
    """Verify the contract and write a new report without overwriting evidence."""

    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing Phase 6 evidence: {output_path}"
        )
    report = build_ablation_contract_report(**paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def load_or_write_ablation_contract_report(
    output_path: Path = DEFAULT_OUTPUT, **paths: Path
) -> dict[str, Any]:
    """Reuse identical evidence or create it once; never overwrite a mismatch."""

    output_path = Path(output_path)
    current = build_ablation_contract_report(**paths)
    if output_path.exists():
        saved = _load_json(output_path, "Phase 6.1 ablation contract")
        if saved != current:
            raise ContractMismatchError(
                f"Existing Phase 6.1 evidence differs from current inputs: {output_path}"
            )
        return saved
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def main() -> None:
    """Support VS Code's Run button while keeping the notebook as the main UI."""

    os.chdir(REPOSITORY_ROOT)
    report = write_ablation_contract_report()
    print(f"Status: {report['status']}")
    print(f"Development folds: {len(report['development_folds'])}")
    print(f"Allowlisted features: {len(report['feature_allowlist'])}")
    print(f"Report written to: {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
