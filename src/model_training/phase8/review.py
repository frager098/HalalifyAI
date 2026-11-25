"""Deterministic, non-tuning review of the Phase 8 reserved evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import fmean
from typing import Any


REVIEW_CONFIG = Path("configs/phase8_review_v1.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def validate_review_inputs(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    """Validate exact Step 8.7 inputs without writing outputs."""
    root = Path(repo_root).resolve()
    config_path = root / REVIEW_CONFIG
    if not config_path.is_file():
        raise FileNotFoundError(f"Missing review contract: {config_path}")
    config = _read_json(config_path)
    identities: dict[str, Any] = {}
    for name, spec in config["required_inputs"].items():
        path = root / spec["path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing Step 8.7 input: {path}")
        actual = _sha256(path)
        if actual != spec["sha256"]:
            raise ValueError(
                f"Hash mismatch for {spec['path']}: expected {spec['sha256']}, got {actual}"
            )
        identities[name] = {"path": spec["path"], "sha256": actual}
    return {"passed": True, "config": config, "identities": identities}


def _sum_matrices(matrices: list[list[list[int]]]) -> list[list[int]]:
    return [
        [sum(matrix[row][column] for matrix in matrices) for column in range(3)]
        for row in range(3)
    ]


def build_review_payload(
    phase7_summary: dict[str, Any],
    phase7_return_report: dict[str, Any],
    phase7_risk_report: dict[str, Any],
    phase8_result: dict[str, Any],
    identities: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the review from already-loaded evidence; no model is fitted."""
    if phase7_summary.get("status") != "complete":
        raise ValueError("Phase 7 summary is not complete.")
    if phase8_result.get("status") != "complete":
        raise ValueError("Phase 8 one-time evaluation is not complete.")
    if phase8_result.get("model_fitting_performed") is not False:
        raise ValueError("Phase 8 unexpectedly reports model fitting.")
    if phase8_result.get("selection_reopened") is not False:
        raise ValueError("Phase 8 unexpectedly reports reopened selection.")

    selected_return = phase7_summary["tasks"]["return"]["selection"]
    selected_risk = phase7_summary["tasks"]["risk"]["selection"]
    if selected_return != {"kind": "simple_benchmark", "benchmark": "momentum_20d"}:
        raise ValueError("Unexpected Phase 7 return selection.")
    if selected_risk != {
        "kind": "simple_benchmark",
        "benchmark": "volatility_20d_with_fold_training_cutoffs",
    }:
        raise ValueError("Unexpected Phase 7 risk selection.")

    return_folds = phase7_return_report["folds"]
    risk_folds = phase7_risk_report["folds"]
    if len(return_folds) != 4 or len(risk_folds) != 4:
        raise ValueError("Step 8.7 expects exactly four Phase 7 development folds.")

    return_spearman = [float(fold["benchmark"]["mean_daily_spearman"]) for fold in return_folds]
    return_spread = [float(fold["benchmark"]["mean_top10_minus_universe"]) for fold in return_folds]
    risk_macro_f1 = [float(fold["benchmark"]["macro_f1"]) for fold in risk_folds]
    risk_high_recall = [float(fold["benchmark"]["high_recall"]) for fold in risk_folds]
    risk_ordinal_mae = [float(fold["benchmark"]["ordinal_mae"]) for fold in risk_folds]
    risk_matrices = [fold["benchmark"]["confusion_matrix"] for fold in risk_folds]
    aggregate_risk_matrix = _sum_matrices(risk_matrices)
    development_high_outcomes = sum(aggregate_risk_matrix[2])
    development_high_to_low = aggregate_risk_matrix[2][0]

    reserved_return = phase8_result["return"]
    reserved_risk = phase8_result["risk"]
    development_return_mean = fmean(return_spearman)
    development_spread_mean = fmean(return_spread)
    development_risk_mean = fmean(risk_macro_f1)
    development_high_recall_mean = fmean(risk_high_recall)
    development_ordinal_mae_mean = fmean(risk_ordinal_mae)
    development_high_to_low_rate = development_high_to_low / development_high_outcomes

    return_value = float(reserved_return["mean_daily_spearman"])
    spread_value = float(reserved_return["mean_top10_minus_universe_return"])
    risk_value = float(reserved_risk["macro_f1"])
    high_recall_value = float(reserved_risk["high_recall"])
    ordinal_mae_value = float(reserved_risk["ordinal_mae"])
    high_to_low_rate = float(reserved_risk["high_to_low_rate"])

    return {
        "schema_version": 1,
        "stage": "phase_8_step_8_7_non_tuning_review",
        "status": "complete",
        "model_fitting_performed": False,
        "selection_reopened": False,
        "post_hoc_threshold_created": False,
        "input_identities": identities,
        "comparison_scope": {
            "development": "Four Phase 7 chronological development folds; previously viewed and not blind test evidence.",
            "reserved": "Single one-time reserved period from 2026-01-02 through 2026-09-30.",
            "rules": config["comparison_rules"],
        },
        "return_review": {
            "procedure": "momentum_20d",
            "development_fold_mean_daily_spearman": return_spearman,
            "development_mean_daily_spearman": development_return_mean,
            "reserved_mean_daily_spearman": return_value,
            "reserved_minus_development_mean": return_value - development_return_mean,
            "reserved_within_development_fold_range": min(return_spearman) <= return_value <= max(return_spearman),
            "development_fold_mean_top10_minus_universe_return": return_spread,
            "development_mean_top10_minus_universe_return": development_spread_mean,
            "reserved_mean_top10_minus_universe_return": spread_value,
            "reserved_minus_development_spread_mean": spread_value - development_spread_mean,
            "finding": "The reserved ranking association is positive and above the development-fold mean, but remains small and within the wide development-fold range. Treat momentum as a weak, regime-variable ranking control, not an expected-return model.",
        },
        "risk_review": {
            "procedure": "volatility_20d_with_training_cutoffs",
            "development_fold_macro_f1": risk_macro_f1,
            "development_mean_macro_f1": development_risk_mean,
            "reserved_macro_f1": risk_value,
            "reserved_minus_development_mean_macro_f1": risk_value - development_risk_mean,
            "reserved_within_development_fold_range": min(risk_macro_f1) <= risk_value <= max(risk_macro_f1),
            "development_mean_high_recall": development_high_recall_mean,
            "reserved_high_recall": high_recall_value,
            "reserved_minus_development_mean_high_recall": high_recall_value - development_high_recall_mean,
            "development_mean_ordinal_mae": development_ordinal_mae_mean,
            "reserved_ordinal_mae": ordinal_mae_value,
            "development_aggregate_high_to_low_count": development_high_to_low,
            "development_aggregate_high_outcomes": development_high_outcomes,
            "development_aggregate_high_to_low_rate": development_high_to_low_rate,
            "reserved_high_to_low_count": int(reserved_risk["high_to_low_count"]),
            "reserved_high_outcomes": int(reserved_risk["high_outcomes"]),
            "reserved_high_to_low_rate": high_to_low_rate,
            "reserved_low_class_recall": float(reserved_risk["per_class"]["Low"]["recall"]),
            "finding": "The reserved risk benchmark is numerically stronger than the development-fold mean for macro F1 and High-risk recall, with a lower serious High-to-Low rate. Low-class recall remains weak, so this is a moderate risk control rather than a uniformly strong classifier.",
        },
        "conclusion": {
            "procedure_decision": "retain_frozen_simple_benchmarks_without_tuning",
            "next_step": "phase_8_step_8_8_publish_and_freeze_conclusion",
            "research_interpretation": "The later-period evidence is reproducible and broadly consistent with Phase 7 benchmark behavior. It supports freezing the simple controls, but not a claim of strong return prediction, uniform risk classification, trading performance, portfolio performance, Shariah compliance, or whole-market generalization.",
        },
        "limitations": list(dict.fromkeys(phase8_result["limitations"] + [
            "Phase 7 consists of four development folds while Phase 8 is one reserved calendar period; their differences are descriptive, not a significance test.",
            "The fixed 50-company universe and 187-session reserved period limit generalization.",
            "The result cannot be used to tune the same procedure while retaining an untouched-test claim.",
        ])),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    ret = payload["return_review"]
    risk = payload["risk_review"]
    conclusion = payload["conclusion"]
    return "\n".join([
        "# Phase 8 Step 8.7 non-tuning review",
        "",
        "## Return benchmark",
        "",
        f"- Phase 7 development-fold mean Spearman: `{ret['development_mean_daily_spearman']}`",
        f"- Phase 8 reserved Spearman: `{ret['reserved_mean_daily_spearman']}`",
        f"- Difference: `{ret['reserved_minus_development_mean']}`",
        f"- Finding: {ret['finding']}",
        "",
        "## Risk benchmark",
        "",
        f"- Phase 7 development-fold mean macro F1: `{risk['development_mean_macro_f1']}`",
        f"- Phase 8 reserved macro F1: `{risk['reserved_macro_f1']}`",
        f"- Phase 8 High-risk recall: `{risk['reserved_high_recall']}`",
        f"- Phase 8 Low-risk recall: `{risk['reserved_low_class_recall']}`",
        f"- Finding: {risk['finding']}",
        "",
        "## Conclusion",
        "",
        conclusion["research_interpretation"],
        "",
        "No tuning or selection change was performed. Step 8.8 is the next gate.",
        "",
    ])


def run_step_8_7_review(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    """Validate evidence and write new-only JSON and Markdown review artifacts."""
    root = Path(repo_root).resolve()
    validation = validate_review_inputs(root)
    config = validation["config"]
    output_json = root / config["outputs"]["json"]
    output_markdown = root / config["outputs"]["markdown"]
    existing = [str(path) for path in (output_json, output_markdown) if path.exists()]
    if existing:
        raise FileExistsError("Step 8.7 outputs already exist and will not be overwritten: " + ", ".join(existing))

    inputs = {
        name: _read_json(root / spec["path"])
        for name, spec in config["required_inputs"].items()
    }
    payload = build_review_payload(
        inputs["phase7_summary"],
        inputs["phase7_return_benchmark_report"],
        inputs["phase7_risk_benchmark_report"],
        inputs["phase8_one_time_evaluation"],
        validation["identities"],
        config,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output_markdown.write_text(_render_markdown(payload), encoding="utf-8")
    return payload
