"""No-fit Phase 7 task review and final evidence publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.phase7.contract import (
    DATASET_PATH,
    ESTIMATOR_ORDER,
    EXPERIMENT_CONTRACT,
    FREEZE_PATH,
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    VARIANT_ORDER,
    _read_json,
)
from src.model_training.phase7.runner import ESTIMATOR_SLUGS


TASK_SUMMARIES = {
    "return": OUTPUT_ROOT / "return" / "return_candidate_summary.json",
    "risk": OUTPUT_ROOT / "risk" / "risk_candidate_summary.json",
}
FINAL_SUMMARY = OUTPUT_ROOT / "phase7_summary.json"
FINAL_FREEZE = Path("configs/phase7_model_freeze_v1.json")
FINAL_REPORT = Path("docs/PHASE7_REPORT.md")


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 7 evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _paired_path(task: str, estimator: str) -> Path:
    return OUTPUT_ROOT / task / ESTIMATOR_SLUGS[estimator] / "paired_summary.json"


def _review_rule(task: str, summary: dict[str, Any]) -> tuple[bool, list[str]]:
    """Apply the predeclared benchmark, consistency, and risk-safety rule."""

    eligible = (
        summary["mean_difference_vs_benchmark"] > 0
        and summary["positive_fold_count_vs_benchmark"] >= 3
    )
    reasons = []
    if summary["mean_difference_vs_benchmark"] <= 0:
        reasons.append("mean primary metric did not beat the benchmark")
    if summary["positive_fold_count_vs_benchmark"] < 3:
        reasons.append("fewer than three folds beat the benchmark")
    if task == "risk":
        if summary["mean_high_recall_difference"] < 0:
            eligible = False
            reasons.append("mean High-risk recall was worse than the benchmark")
        if summary["high_to_low_count_difference"] > 0:
            eligible = False
            reasons.append("serious High-to-Low errors increased")
    if eligible:
        reasons.append("passed the predeclared benchmark and consistency rules")
    return eligible, reasons


def _option(
    task: str,
    estimator: str,
    variant: str,
    paired: dict[str, Any],
) -> dict[str, Any]:
    summary = paired[variant]
    eligible, reasons = _review_rule(task, summary)
    return {
        "estimator": estimator,
        "variant": variant,
        "primary_metric": summary["primary_metric"],
        "mean_primary": summary["mean_primary"],
        "benchmark_mean_primary": summary["benchmark_mean_primary"],
        "mean_difference_vs_benchmark": summary["mean_difference_vs_benchmark"],
        "positive_fold_count_vs_benchmark": summary[
            "positive_fold_count_vs_benchmark"
        ],
        "eligible_to_advance": eligible,
        "reasons": reasons,
        "summary": summary,
        "evidence_path": str(_paired_path(task, estimator)),
        "evidence_sha256": sha256(_paired_path(task, estimator)),
    }


def review_task(task: str, output: Path | None = None) -> dict[str, Any]:
    """Apply the frozen review rule to existing model reports without fitting."""

    if task not in {"return", "risk"}:
        raise ValueError("Task must be 'return' or 'risk'")
    output = Path(output or TASK_SUMMARIES[task])
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 7 review: {output}")
    freeze = _read_json(FREEZE_PATH, "Phase 6 v2 freeze")
    contract = _read_json(EXPERIMENT_CONTRACT, "Phase 7 experiment contract")
    options = []
    for estimator in ESTIMATOR_ORDER:
        paired = _read_json(_paired_path(task, estimator), f"{task} {estimator} evidence")
        if paired.get("status") != "complete" or paired.get("task") != task:
            raise ValueError(f"Invalid {task} {estimator} evidence")
        for variant in VARIANT_ORDER:
            options.append(_option(task, estimator, variant, paired))

    eligible = [option for option in options if option["eligible_to_advance"]]
    if eligible:
        # max() preserves declared estimator/variant order on an exact tie.
        selected = max(eligible, key=lambda option: option["mean_primary"])
        decision = "advance_learned_option"
        selected_features = (
            freeze["original_phase5_features"]
            if selected["variant"] == "comparator"
            else freeze["tasks"][task]["candidate_features"]
        )
        rationale = (
            f"{selected['estimator']} {selected['variant']} passed the fixed "
            "benchmark, fold-consistency, and task-safety rules."
        )
        selection = {
            "kind": "learned_model",
            "estimator": selected["estimator"],
            "variant": selected["variant"],
            "features": selected_features,
            "tuning_rule": contract["tuning_rule"],
        }
    else:
        decision = "retain_simple_benchmark"
        benchmark = "momentum_20d" if task == "return" else "volatility_20d_with_fold_training_cutoffs"
        rationale = (
            "No learned option passed every predeclared benchmark, consistency, "
            "and safety requirement."
        )
        selection = {"kind": "simple_benchmark", "benchmark": benchmark}

    report = {
        "schema_version": 1,
        "stage": f"phase_7_{task}_review",
        "status": "complete",
        "model_fitting_performed": False,
        "task": task,
        "decision": decision,
        "selection": selection,
        "rationale": rationale,
        "options": options,
        "dataset_sha256": sha256(DATASET_PATH),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "freeze_sha256": sha256(FREEZE_PATH),
        "experiment_contract_sha256": sha256(EXPERIMENT_CONTRACT),
        "limitations": freeze["limitations"],
    }
    _write_new(output, json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def _markdown(summary: dict[str, Any]) -> str:
    return_report = summary["tasks"]["return"]
    risk_report = summary["tasks"]["risk"]
    return f"""# Phase 7 candidate-tuning report

## Scope

Phase 7 compared the frozen return and risk candidates on four chronological
development folds. These are development results, not an untouched final test,
trading result, or portfolio result.

## Return decision

- Decision: `{return_report['decision']}`
- Selection: `{json.dumps(return_report['selection'], sort_keys=True)}`
- Reason: {return_report['rationale']}

## Risk decision

- Decision: `{risk_report['decision']}`
- Selection: `{json.dumps(risk_report['selection'], sort_keys=True)}`
- Reason: {risk_report['rationale']}

## Frozen evidence

- Dataset SHA-256: `{summary['dataset_sha256']}`
- Protocol SHA-256: `{summary['protocol_sha256']}`
- Phase 6 freeze SHA-256: `{summary['phase6_freeze_sha256']}`
- Phase 7 experiment contract SHA-256: `{summary['experiment_contract_sha256']}`

## Limitations and Phase 8 gate

- The 50-stock universe has survivorship and selection bias.
- Twenty-session outcomes overlap, so daily rows are not independent trials.
- The 2024–2025 period was previously viewed and is not a fresh test.
- No SEC fundamental feature was approved for these models.
- Phase 8 requires a genuinely later verified period frozen before its outcomes
  are inspected. Any changed model requires a different future evaluation.
"""


def finalize_phase7(
    summary_path: Path = FINAL_SUMMARY,
    freeze_path: Path = FINAL_FREEZE,
    report_path: Path = FINAL_REPORT,
) -> dict[str, Any]:
    """Publish Step 7.10 from completed reviews without fitting or extra search."""

    targets = [Path(summary_path), Path(freeze_path), Path(report_path)]
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite Phase 7 conclusion: " + ", ".join(existing))
    return_report = _read_json(TASK_SUMMARIES["return"], "return review")
    risk_report = _read_json(TASK_SUMMARIES["risk"], "risk review")
    phase6_freeze = _read_json(FREEZE_PATH, "Phase 6 v2 freeze")
    contract = _read_json(EXPERIMENT_CONTRACT, "Phase 7 experiment contract")
    summary = {
        "schema_version": 1,
        "stage": "phase_7_step_7_10_conclusion",
        "status": "complete",
        "model_fitting_performed": False,
        "dataset_sha256": sha256(DATASET_PATH),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "phase6_freeze_sha256": sha256(FREEZE_PATH),
        "experiment_contract_sha256": sha256(EXPERIMENT_CONTRACT),
        "tasks": {"return": return_report, "risk": risk_report},
        "phase8_gate": (
            "Freeze the selected procedure before inspecting a genuinely later "
            "verified period. The reused 2024-2025 period is not a blind test."
        ),
        "limitations": phase6_freeze["limitations"],
    }
    model_freeze = {
        "schema_version": 1,
        "stage": "phase_7_model_selection_freeze",
        "status": "frozen_for_phase_8_evaluation",
        "dataset_sha256": summary["dataset_sha256"],
        "protocol_sha256": summary["protocol_sha256"],
        "return": return_report["selection"],
        "risk": risk_report["selection"],
        "estimators": contract["estimators"],
        "decision_rules": {
            "return": contract["return_decision_rule"],
            "risk": contract["risk_decision_rule"],
        },
        "phase8_gate": summary["phase8_gate"],
    }
    _write_new(Path(summary_path), json.dumps(summary, indent=2, allow_nan=False) + "\n")
    _write_new(Path(freeze_path), json.dumps(model_freeze, indent=2, allow_nan=False) + "\n")
    _write_new(Path(report_path), _markdown(summary))
    return summary
