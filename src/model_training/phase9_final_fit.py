"""Student-run Phase 9.2c development fit. No viewed-period evaluation."""

from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.model_training.baseline_models import _return_ranking, fold_roles
from src.model_training.chronological_evaluation_protocol import _hash_keys, _role, apply_risk_boundaries


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs(config_path: Path) -> tuple[dict, pd.DataFrame, dict, dict, dict]:
    """Check frozen identities and roles before any model fitting."""
    spec = json.loads(config_path.read_text(encoding="utf-8"))
    if spec["schema_version"] != 1 or spec["status"] != "frozen_before_student_fit":
        raise ValueError("Unexpected final-fit contract")
    for name, item in spec["inputs"].items():
        path = Path(item["path"])
        if not path.is_file() or digest(path) != item["sha256"]:
            raise ValueError(f"Missing or changed {name}: {path}")
    protocol = json.loads(Path(spec["inputs"]["protocol"]["path"]).read_text(encoding="utf-8"))
    prior = json.loads(Path(spec["inputs"]["phase7_contract"]["path"]).read_text(encoding="utf-8"))
    inference = json.loads(Path(spec["inputs"]["inference_contract"]["path"]).read_text(encoding="utf-8"))
    comparison = json.loads(Path(spec["inputs"]["phase9_comparison"]["path"]).read_text(encoding="utf-8"))
    comparison_manifest = json.loads(Path(spec["inputs"]["phase9_comparison_manifest"]["path"]).read_text(encoding="utf-8"))
    if (protocol["test_start"] != spec["final_refit"]["session_date_before"]
            or spec["final_refit"]["target_window_end_before"] != protocol["test_start"]
            or len(protocol["folds"]) != 4):
        raise ValueError("Final refit boundary differs from frozen chronology")
    if comparison_manifest["dataset_sha256"] != spec["inputs"]["dataset"]["sha256"] or len(comparison) != 76:
        raise ValueError("Phase 9.2b comparison identity or row count changed")
    fold = protocol["folds"][spec["selection"]["validation_fold"] - 1]
    if (fold["fold"] != 4 or fold["inner_first"] != spec["selection"]["validation_start"]
            or fold["inner_last"] != spec["selection"]["validation_end"]
            or spec["selection"]["training_target_window_end_before"] != fold["inner_first"]):
        raise ValueError("Selected inner validation role changed")
    if len([row for row in comparison if row["factor"] == "baseline"]) != 8:
        raise ValueError("Phase 9.2b is missing baseline fold records")
    if (spec["selection"]["return_C_grid"] != protocol["experiment_protocol"]["search_budget"]["logistic_C"]
            or spec["selection"]["risk_max_leaf_nodes_grid"] != protocol["experiment_protocol"]["search_budget"]["hist_gbm_max_leaf_nodes"]):
        raise ValueError("Final selection grid differs from frozen grid")
    for task in ("return", "risk"):
        if prior["tasks"][task]["candidate_features"] != inference[task]["feature_order"]:
            raise ValueError(f"{task} feature order differs from inference contract")
    frame = pd.read_csv(Path(spec["inputs"]["dataset"]["path"]), low_memory=False)
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/session_date keys")
    for task in ("return", "risk"):
        train, validation = fold_roles(frame, fold, task, "inner")
        if (train.target_window_end.max() >= validation.session_date.min()
                or validation.session_date.min() != spec["selection"]["first_eligible_validation_session"]
                or validation.session_date.max() != spec["selection"]["last_eligible_validation_session"]):
            raise ValueError(f"{task}: frozen eligible validation dates or purge changed")
    return spec, frame, protocol, prior, inference


def _features(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    values = rows[columns].copy()
    if values.empty or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Empty or nonfinite selected features")
    return values


def _model(task: str, selected: dict, spec: dict):
    if task == "return":
        return make_pipeline(StandardScaler(), LogisticRegression(
            C=selected["C"], **spec["final_refit"]["return_fixed"]))
    return HistGradientBoostingClassifier(
        max_leaf_nodes=selected["max_leaf_nodes"], **spec["final_refit"]["risk_fixed"])


def _labels(task: str, train: pd.DataFrame, validation: pd.DataFrame | None = None):
    if task == "return":
        first = train.relative_return_class.astype(int).to_numpy()
        second = None if validation is None else validation.relative_return_class.astype(int).to_numpy()
        return first, second, None
    boundaries = train.risk_volatility_next_20d.quantile([1 / 3, 2 / 3]).tolist()
    if not np.isfinite(boundaries).all() or boundaries[0] >= boundaries[1]:
        raise ValueError("Invalid training-derived risk boundaries")
    first = apply_risk_boundaries(train.risk_volatility_next_20d, boundaries)
    second = None if validation is None else apply_risk_boundaries(validation.risk_volatility_next_20d, boundaries)
    return first, second, boundaries


def _select(task: str, train: pd.DataFrame, validation: pd.DataFrame,
            columns: list[str], spec: dict) -> dict:
    if train.target_window_end.max() >= validation.session_date.min():
        raise ValueError("Training target window overlaps validation")
    x_train, x_validation = _features(train, columns), _features(validation, columns)
    y_train, y_validation, boundaries = _labels(task, train, validation)
    grid = ([{"C": value} for value in spec["selection"]["return_C_grid"]] if task == "return"
            else [{"max_leaf_nodes": value} for value in spec["selection"]["risk_max_leaf_nodes_grid"]])
    candidates = []
    for params in grid:
        model = _model(task, params, spec)
        model.fit(x_train, y_train)
        probabilities = model.predict_proba(x_validation)
        if not np.array_equal(model[-1].classes_ if task == "return" else model.classes_, [0, 1, 2]):
            raise ValueError("Unexpected validation model class order")
        if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1):
            raise ValueError("Invalid validation probabilities")
        score = (_return_ranking(validation, probabilities[:, 2] - probabilities[:, 0])["mean_daily_spearman"]
                 if task == "return" else f1_score(y_validation, probabilities.argmax(axis=1),
                                                    labels=[0, 1, 2], average="macro", zero_division=0))
        if score is None or not np.isfinite(score):
            raise ValueError("Undefined validation primary score")
        candidates.append({"parameters": params, "primary_score": float(score)})
    selected = max(candidates, key=lambda item: item["primary_score"])["parameters"]
    return {"selected_parameters": selected, "candidates": candidates,
            "inner_training": _role_summary(train, y_train),
            "inner_validation": _role_summary(validation, y_validation),
            "inner_training_risk_boundaries": boundaries,
            "primary_metric": spec["selection"]["return_metric" if task == "return" else "risk_metric"]}


def _role_summary(rows: pd.DataFrame, labels: np.ndarray) -> dict:
    return {"rows": len(rows), "tickers": int(rows.ticker.nunique()),
            "first_session": str(rows.session_date.min()), "last_session": str(rows.session_date.max()),
            "max_target_window_end": str(rows.target_window_end.max()),
            "keys_sha256": _hash_keys(rows),
            "class_counts": np.bincount(labels, minlength=3).tolist()}


def run_final_fit(config_path: Path, output: Path, verified=None) -> dict:
    """Select on one frozen inner block; refit only on knowable development labels."""
    if output.exists():
        raise FileExistsError(f"Preserve existing final-fit evidence: {output}")
    spec, frame, protocol, prior, inference = verified or verify_inputs(config_path)
    if output != Path(spec["output"]):
        raise ValueError("Output location differs from frozen contract")
    fold = protocol["folds"][spec["selection"]["validation_fold"] - 1]
    selections, models, fit_reports = {}, {}, {}
    for task in ("return", "risk"):
        train, validation = fold_roles(frame, fold, task, "inner")
        # Fold boundaries are scheduled dates. The frozen eligible role starts
        # one session later and ends earlier after the 20-session label purge.
        if (train.target_window_end.max() >= validation.session_date.min()
                or validation.session_date.min() != spec["selection"]["first_eligible_validation_session"]
                or validation.session_date.max() != spec["selection"]["last_eligible_validation_session"]):
            raise ValueError("Frozen inner role or purge failed")
        columns = list(prior["tasks"][task]["candidate_features"])
        selections[task] = _select(task, train, validation, columns, spec)
        # _role applies the frozen eligibility flag and purges all labels that
        # would require prices from the viewed period beginning 2024-07-01.
        dates = sorted(frame.loc[frame.session_date.lt(protocol["test_start"]), "session_date"].unique())
        final_rows = _role(frame, dates, protocol["test_start"], task=task)
        if (final_rows.empty or final_rows.session_date.max() >= protocol["test_start"]
                or final_rows.target_window_end.max() >= protocol["test_start"]
                or not final_rows[task + "_eligible"].all()):
            raise ValueError("Final fitting role enters viewed period or is empty")
        x_final = _features(final_rows, columns)
        y_final, _, boundaries = _labels(task, final_rows)
        model = _model(task, selections[task]["selected_parameters"], spec)
        model.fit(x_final, y_final)
        classes = model[-1].classes_ if task == "return" else model.classes_
        if not np.array_equal(classes, [0, 1, 2]):
            raise ValueError("Unexpected final class order")
        sample = model.predict_proba(x_final.head(5))
        if not np.isfinite(sample).all() or not np.allclose(sample.sum(axis=1), 1):
            raise ValueError("Final model returned invalid probabilities")
        models[task] = model
        fit_reports[task] = {"estimator": inference[task]["estimator"], "feature_order": columns,
                             "class_order": inference[task]["class_order"],
                             "selected_parameters": selections[task]["selected_parameters"],
                             "risk_boundaries": boundaries, "training": _role_summary(final_rows, y_final)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    artifacts = {}
    for task in ("return", "risk"):
        path = output / f"{task}_model.joblib"
        joblib.dump(models[task], path)
        artifacts[task] = {"path": str(path), "sha256": digest(path)}
    manifest = {"schema_version": 1, "stage": "phase_9_step_9_2c_final_fit",
                "evidence_status": "development_only", "untouched_test_claim": False,
                "config_sha256": digest(config_path), "input_sha256": {name: item["sha256"] for name, item in spec["inputs"].items()},
                "code_sha256": {"src/model_training/phase9_final_fit.py": digest(Path(__file__)),
                                "src/model_training/baseline_models.py": digest(Path("src/model_training/baseline_models.py")),
                                "src/model_training/chronological_evaluation_protocol.py": digest(Path("src/model_training/chronological_evaluation_protocol.py"))},
                "dependencies": {"python": platform.python_version(), **{name: version(name) for name in
                                  ("numpy", "pandas", "scipy", "scikit-learn", "joblib")}},
                "selection": selections, "final_fit": fit_reports, "artifacts": artifacts,
                "package_allowed": False,
                "limitations": [spec["known_limitation"], "Viewed 2026 period was not used for selection or final fit."]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
