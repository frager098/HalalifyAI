"""Student-run Phase 9 development comparisons. Never reads the viewed 2026 set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.model_training.baseline_models import _return_ranking, fold_roles
from src.model_training.chronological_evaluation_protocol import apply_risk_boundaries


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs(contract_path: Path) -> tuple[dict, pd.DataFrame, dict]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    dataset = Path(contract["source_dataset"])
    protocol_path = Path(contract["fold_source"])
    for path, expected in ((dataset, contract["dataset_sha256"]),
                           (protocol_path, contract["fold_sha256"])):
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Missing or changed frozen input: {path}")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(dataset, low_memory=False)
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/date keys")
    if len(protocol["folds"]) != 4 or protocol["test_start"] != "2024-07-01":
        raise ValueError("Unexpected fold protocol")
    return contract, frame, protocol


def split_inner(train: pd.DataFrame, validation: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split the 126 scheduled inner sessions; purge labels at both boundaries."""
    dates = sorted(validation.session_date.unique())
    # The frozen role already excludes the final target-overlap dates.
    if len(dates) < 100:
        raise ValueError("Inner role has too few observed sessions")
    boundary = dates[63]
    tune = validation.loc[(validation.session_date < boundary) &
                          (validation.target_window_end < boundary)].copy()
    later = validation.loc[validation.session_date >= boundary].copy()
    if train.target_window_end.max() >= tune.session_date.min():
        raise ValueError("Training target overlaps tuning")
    if tune.empty or later.empty or tune.target_window_end.max() >= later.session_date.min():
        raise ValueError("Tuning target overlaps calibration")
    return train, tune, later


def _labels(task: str, train: pd.DataFrame, rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[float] | None]:
    if task == "return":
        return train.relative_return_class.astype(int).to_numpy(), rows.relative_return_class.astype(int).to_numpy(), None
    boundaries = train.risk_volatility_next_20d.quantile([1 / 3, 2 / 3]).tolist()
    if not np.isfinite(boundaries).all() or boundaries[0] >= boundaries[1]:
        raise ValueError("Invalid training-derived risk boundaries")
    return apply_risk_boundaries(train.risk_volatility_next_20d, boundaries), apply_risk_boundaries(rows.risk_volatility_next_20d, boundaries), boundaries


def _features(task: str, variant: str, base: list[str], rows: pd.DataFrame) -> pd.DataFrame:
    columns = list(base)
    if variant == "original_14":
        columns = columns[:14]
    elif variant == "drop_momentum_20d":
        columns.remove("momentum_20d")
    elif variant == "drop_sma50":
        columns.remove("price_to_sma50")
    elif variant == "drop_volatility_60d":
        columns.remove("volatility_60d")
    elif variant == "peer_zscore":
        for name in ("momentum_5d", "momentum_20d", "momentum_60d"):
            values = rows.groupby("session_date")[name]
            mean, std = values.transform("mean"), values.transform("std")
            rows = rows.copy()
            rows[name] = (rows[name] - mean) / std.replace(0, np.nan)
    if task == "risk" and variant in {"original_14", "drop_momentum_20d", "peer_zscore"}:
        raise ValueError("Return feature variant used for risk")
    result = rows[columns].copy()
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError(f"Missing or nonfinite {variant} features")
    return result


def _model(task: str, params: dict):
    if task == "return":
        core = LogisticRegression(C=params.get("C", 0.1), class_weight=params.get("class_weight"),
                                  max_iter=1000, solver="lbfgs")
        return core if params.get("scaling") == "none" else make_pipeline(StandardScaler(), core)
    return HistGradientBoostingClassifier(learning_rate=params.get("learning_rate", 0.1),
                                          max_iter=params.get("max_iter", 100),
                                          max_leaf_nodes=params.get("max_leaf_nodes", 31),
                                          min_samples_leaf=params.get("min_samples_leaf", 20),
                                          l2_regularization=params.get("l2_regularization", 0.0),
                                          early_stopping=False, random_state=42)


def _calibrated_probabilities(model, fit_x, fit_y, calibration_x, calibration_y, evaluation_x):
    """Fit three sigmoid calibrators on later data, normalize their outputs."""
    model.fit(fit_x, fit_y)
    raw_cal = model.predict_proba(calibration_x)
    raw_eval = model.predict_proba(evaluation_x)
    calibrated = []
    for cls in range(3):
        binary = (calibration_y == cls).astype(int)
        if len(np.unique(binary)) != 2:
            raise ValueError("Calibration block lacks a class")
        calibrator = LogisticRegression(max_iter=1000)
        calibrator.fit(raw_cal[:, [cls]], binary)
        calibrated.append(calibrator.predict_proba(raw_eval[:, [cls]])[:, 1])
    values = np.column_stack(calibrated)
    return values / values.sum(axis=1, keepdims=True)


def _special_variant(task, variant, base, train, tuning, calibration, evaluation):
    """Fit, tune, then calibrate or stop on disjoint chronological roles."""
    if (train.target_window_end.max() >= tuning.session_date.min()
            or tuning.target_window_end.max() >= calibration.session_date.min()
            or calibration.target_window_end.max() >= evaluation.session_date.min()):
        raise ValueError("Special variant has overlapping target windows")
    x_train = _features(task, "baseline", base, train)
    x_tune = _features(task, "baseline", base, tuning)
    x_cal = _features(task, "baseline", base, calibration)
    x_eval = _features(task, "baseline", base, evaluation)
    y_train, y_tune, boundaries = _labels(task, train, tuning)
    _, y_cal, _ = _labels(task, train, calibration)
    _, y_eval, _ = _labels(task, train, evaluation)
    if variant == "sigmoid_calibration":
        if task != "return":
            raise ValueError("Return calibration variant requested for risk")
        # Select C only on the earlier tuning role.
        candidates = []
        for c in (0.1, 1.0, 10.0):
            model = _model(task, {"C": c})
            model.fit(x_train, y_train)
            score = _score(task, tuning, y_tune, model.predict_proba(x_tune))["mean_daily_spearman"]
            candidates.append((c, score))
        selected = max(candidates, key=lambda item: item[1])[0]
        probability = _calibrated_probabilities(_model(task, {"C": selected}), x_train, y_train, x_cal, y_cal, x_eval)
        return probability, y_eval, boundaries, {"C": selected, "calibration": "sigmoid"}, candidates
    if variant == "chronological_early_stopping":
        if task != "risk":
            raise ValueError("Risk stop variant requested for return")
        candidates = []
        for iterations in (25, 50, 100, 150, 200):
            model = _model(task, {"max_iter": iterations})
            model.fit(x_train, y_train)
            score = _score(task, tuning, y_tune, model.predict_proba(x_tune))["macro_f1"]
            candidates.append((iterations, score))
        selected = max(candidates, key=lambda item: item[1])[0]
        # The later block checks the selected stop setting without fitting on it.
        model = _model(task, {"max_iter": selected})
        model.fit(x_train, y_train)
        _score(task, calibration, y_cal, model.predict_proba(x_cal))
        return model.predict_proba(x_eval), y_eval, boundaries, {"max_iter": selected, "early_stopping": "chronological"}, candidates
    raise ValueError("Unknown special variant")


def _score(task: str, rows: pd.DataFrame, truth: np.ndarray, probabilities: np.ndarray) -> dict:
    prediction = probabilities.argmax(axis=1)
    result = {"macro_f1": float(f1_score(truth, prediction, labels=[0, 1, 2], average="macro", zero_division=0)),
              "log_loss": float(log_loss(truth, probabilities, labels=[0, 1, 2])),
              "multiclass_brier": float(np.mean(np.sum((probabilities - np.eye(3)[truth]) ** 2, axis=1)))}
    if task == "return":
        result["mean_daily_spearman"] = _return_ranking(rows, probabilities[:, 2] - probabilities[:, 0])["mean_daily_spearman"]
    else:
        result["high_recall"] = float(recall_score(truth, prediction, labels=[2], average="macro", zero_division=0))
        result["high_to_low"] = int(np.sum((truth == 2) & (prediction == 0)))
    return result


def run_comparison(contract_path: Path, output: Path) -> dict:
    """Fit predeclared development candidates; student invokes this from notebook."""
    contract, frame, protocol = verify_inputs(contract_path)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite experiment evidence: {output}")
    reports, predictions, role_summaries = [], [], []
    phase7_contract = Path("reports/model_evaluation/phase7_candidate_tuning_v1/experiment_contract.json")
    if not phase7_contract.is_file() or digest(phase7_contract) != "d817a11916228a2af9709daf78dbfca0ecc150f5ab3d45155fed84fd2c42d8fa":
        raise ValueError("Missing or changed Phase 7 candidate specification")
    phase7_features = json.loads(phase7_contract.read_text(encoding="utf-8"))["tasks"]
    for fold in protocol["folds"]:
        for task in ("return", "risk"):
            inner_train, inner_validation = fold_roles(frame, fold, task, "inner")
            outer_train, outer_eval = fold_roles(frame, fold, task, "outer")
            if fold["outer_last"] >= protocol["test_start"]:
                raise ValueError("Development fold enters viewed period")
            base = list(phase7_features[task]["candidate_features"])
            prior_report = Path(f"reports/model_evaluation/phase7_candidate_tuning_v1/{task}/" +
                                ("logistic_regression" if task == "return" else "hist_gradient_boosting") +
                                "/candidate_report.json")
            expected_report_hash = {
                "return": "2517e4b4e489edfda96534fcc2e9877fb6c10ce2ca28ee27b5cac28f82f44d4e",
                "risk": "903de0f71b9c80009b4cfb4874bd5ce4f8f6343ae1c36a51fea0051391056919",
            }[task]
            if not prior_report.is_file() or digest(prior_report) != expected_report_hash:
                raise ValueError(f"Missing or changed Phase 7 {task} candidate report: {prior_report}")
            prior = json.loads(prior_report.read_text(encoding="utf-8"))
            selected_prior = prior["folds"][fold["fold"] - 1]["selected_parameters"]
            baseline_params = {"C": selected_prior["C"]} if task == "return" else {"max_leaf_nodes": selected_prior["max_leaf_nodes"]}
            variants = [("baseline", baseline_params)]
            if task == "return":
                variants += [("C_0.1", {"C": 0.1}), ("C_1", {"C": 1.0}), ("C_10", {"C": 10.0}),
                             ("balanced", {"class_weight": "balanced"}), ("no_scaling", {"scaling": "none"}),
                             ("original_14", {}), ("drop_momentum_20d", {}), ("peer_zscore", {})]
            else:
                for parameter, values in (("learning_rate", [0.05, 0.1]), ("max_iter", [100, 200]),
                                          ("max_leaf_nodes", [15, 31, 63]), ("min_samples_leaf", [20, 50]),
                                          ("l2_regularization", [0.0, 1.0])):
                    variants += [(f"{parameter}_{value}", {parameter: value}) for value in values]
                variants += [("drop_sma50", {}), ("drop_volatility_60d", {})]
            # Select each named factor from earlier inner validation only.
            groups: dict[str, list[tuple[str, dict]]] = {"baseline": [("baseline", baseline_params)]}
            for variant, params in variants[1:]:
                factor = next((name for name in ("learning_rate", "max_iter", "max_leaf_nodes", "min_samples_leaf", "l2_regularization") if variant.startswith(name + "_")), variant)
                groups.setdefault(factor, [("baseline", baseline_params)]).append((variant, {**baseline_params, **params}))
            for factor, options in groups.items():
                inner_scores = []
                for option_name, option_params in options:
                    option_features = option_name if option_name in {"original_14", "drop_momentum_20d", "peer_zscore", "drop_sma50", "drop_volatility_60d"} else "baseline"
                    x_inner = _features(task, option_features, base, inner_train)
                    x_validation = _features(task, option_features, base, inner_validation)
                    y_inner, y_validation, _ = _labels(task, inner_train, inner_validation)
                    candidate = _model(task, option_params)
                    candidate.fit(x_inner, y_inner)
                    score = _score(task, inner_validation, y_validation, candidate.predict_proba(x_validation))
                    primary = score["mean_daily_spearman" if task == "return" else "macro_f1"]
                    inner_scores.append((option_name, option_params, primary))
                # max keeps baseline first on an exact tie.
                variant, params, selected_inner_score = max(inner_scores, key=lambda item: item[2])
                feature_variant = variant if variant in {"original_14", "drop_momentum_20d", "peer_zscore", "drop_sma50", "drop_volatility_60d"} else "baseline"
                train_x, eval_x = _features(task, feature_variant, base, outer_train), _features(task, feature_variant, base, outer_eval)
                y_train, y_eval, boundaries = _labels(task, outer_train, outer_eval)
                model = _model(task, params)
                model.fit(train_x, y_train)
                if not np.array_equal(model.classes_ if task == "risk" else model[-1].classes_ if hasattr(model, "steps") else model.classes_, [0, 1, 2]):
                    raise ValueError("Unexpected class order")
                probability = model.predict_proba(eval_x)
                if not np.isfinite(probability).all() or not np.allclose(probability.sum(axis=1), 1):
                    raise ValueError("Invalid probabilities")
                metrics = _score(task, outer_eval, y_eval, probability)
                reports.append({"fold": fold["fold"], "task": task, "factor": factor, "variant": variant,
                                "parameters": params, "inner_primary": selected_inner_score,
                                "inner_candidates": [{"variant": name, "parameters": settings, "primary": score}
                                                     for name, settings, score in inner_scores],
                                "rows": len(outer_eval), "risk_boundaries": boundaries, "metrics": metrics})
                part = outer_eval[["ticker", "session_date", "target_window_end"]].copy()
                part.insert(0, "fold", fold["fold"])
                part["task"], part["variant"], part["truth"] = task, variant, y_eval
                for index, name in enumerate(("p_0", "p_1", "p_2")):
                    part[name] = probability[:, index]
                predictions.append(part)
            special = "sigmoid_calibration" if task == "return" else "chronological_early_stopping"
            fit_rows, tune_rows, cal_rows = split_inner(inner_train, inner_validation)
            role_summaries.append({"fold": fold["fold"], "task": task,
                                   "inner_train_rows": len(inner_train), "inner_validation_rows": len(inner_validation),
                                   "outer_train_rows": len(outer_train), "outer_evaluation_rows": len(outer_eval),
                                   "special_fit_rows": len(fit_rows), "special_tune_rows": len(tune_rows),
                                   "special_calibration_rows": len(cal_rows),
                                   "max_fit_target_end": str(fit_rows.target_window_end.max()),
                                   "first_tune_date": str(tune_rows.session_date.min()),
                                   "max_tune_target_end": str(tune_rows.target_window_end.max()),
                                   "first_calibration_date": str(cal_rows.session_date.min()),
                                   "first_outer_date": str(outer_eval.session_date.min())})
            probability, y_eval, boundaries, params, candidates = _special_variant(
                task, special, base, fit_rows, tune_rows, cal_rows, outer_eval)
            reports.append({"fold": fold["fold"], "task": task, "factor": special,
                            "variant": special, "parameters": params, "inner_candidates": candidates,
                            "rows": len(outer_eval), "risk_boundaries": boundaries,
                            "metrics": _score(task, outer_eval, y_eval, probability)})
            part = outer_eval[["ticker", "session_date", "target_window_end"]].copy()
            part.insert(0, "fold", fold["fold"])
            part["task"], part["variant"], part["truth"] = task, special, y_eval
            for index, name in enumerate(("p_0", "p_1", "p_2")):
                part[name] = probability[:, index]
            predictions.append(part)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"contract_sha256": digest(contract_path), "dataset_sha256": contract["dataset_sha256"],
                "fold_sha256": contract["fold_sha256"], "code_sha256": digest(Path(__file__)),
                "phase7_contract_sha256": digest(phase7_contract),
                "phase7_reports_sha256": {task: digest(Path(f"reports/model_evaluation/phase7_candidate_tuning_v1/{task}/" +
                     ("logistic_regression" if task == "return" else "hist_gradient_boosting") + "/candidate_report.json"))
                     for task in ("return", "risk")},
                "status": "development_only", "model_fitting_performed": True}
    (output / "input_hash_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "candidate_results.json").write_text(json.dumps(reports, indent=2, allow_nan=False), encoding="utf-8")
    (output / "fold_roles.json").write_text(json.dumps(role_summaries, indent=2), encoding="utf-8")
    pd.concat(predictions, ignore_index=True).to_csv(output / "outer_predictions.csv", index=False)
    (output / "selection_review.md").write_text(
        "# Phase 9 development selection review\n\n"
        "Inspect candidate_results.json across all four folds. Apply the frozen return consistency "
        "and risk safety rules before selecting a change. No automatic promotion or untouched-test claim.\n",
        encoding="utf-8")
    return {"output": str(output), "comparisons": len(reports), "manifest": manifest}
