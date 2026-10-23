"""Phase 5.8: risk HistGradientBoosting on frozen chronological folds.

Run: python -m src.modeling.phase5_risk_histgbm --output-dir reports/generated/phase5_risk_histgbm
"""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import f1_score

from src.features.build_dataset import sha256
from src.modeling.evaluation_protocol import _hash_keys, apply_risk_boundaries
from src.modeling.phase5_baselines import (
    DEFAULT_DATA, DEFAULT_PROTOCOL, fold_roles, matched_feature_sets, verify_inputs,
)
from src.modeling.phase5_return_histgbm import fit_predict
from src.modeling.phase5_return_logistic import _role_log
from src.modeling.phase5_risk_logistic import _probability_metrics

DEFAULT_LOGISTIC_DIR = Path("reports/generated/phase5_risk_logistic")
EXPECTED_FIXED = {"max_iter": 100, "learning_rate": 0.1,
                  "early_stopping": False, "random_state": 42}


def _compare_logistic(rows, directory):
    """Require the earlier risk model's saved cohort and labels to match."""
    directory = Path(directory)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    path = directory / "outer_predictions.csv"
    if report["stage"] != "phase5_step_5_7" or sha256(path) != report["prediction_sha256"]:
        raise ValueError("Saved risk Logistic Regression artifact is invalid")
    previous = pd.read_csv(path)
    shared = ["fold", "ticker", "session_date", "target_window_end",
              "risk_volatility_next_20d", "fold_risk_class",
              "prior_p_low", "prior_p_medium", "prior_p_high", "prior_predicted_class"]
    if len(previous) != len(rows):
        raise ValueError("Risk model evaluation row counts differ")
    exact = ["fold", "ticker", "session_date", "target_window_end",
             "fold_risk_class", "prior_predicted_class"]
    numeric = [column for column in shared if column not in exact]
    if not previous[exact].equals(rows[exact]) or not np.allclose(
            previous[numeric], rows[numeric], rtol=0, atol=1e-12):
        raise ValueError("Risk model evaluation keys, classes or priors differ")
    return report["prediction_sha256"]


def run(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL,
        logistic_dir=DEFAULT_LOGISTIC_DIR, output_dir=None):
    frame, _, protocol = verify_inputs(data_path, protocol_path)
    budget = protocol["experiment_protocol"]["search_budget"]
    grid, fixed = budget["hist_gbm_max_leaf_nodes"], budget["hist_gbm_fixed"]
    if grid != [15, 31, 63] or fixed != EXPECTED_FIXED:
        raise ValueError("Frozen boosted-tree settings mismatch")
    logs, prediction_parts = [], []
    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, "risk", "inner")
        outer_train, outer_eval = fold_roles(frame, fold, "risk", "outer")
        if (inner_train.target_window_end.max() >= fold["inner_first"] or
                inner_eval.target_window_end.max() >= fold["outer_first"] or
                outer_train.target_window_end.max() >= fold["outer_first"]):
            raise ValueError("Risk outcome window overlaps a fold boundary")
        inner_saved = fold["tasks"]["risk"]["inner"]
        outer_saved = fold["tasks"]["risk"]["outer"]
        inner_cutoffs = inner_saved["risk_boundaries"]
        outer_cutoffs = outer_saved["risk_boundaries"]
        y_inner_train = apply_risk_boundaries(inner_train.risk_volatility_next_20d, inner_cutoffs)
        y_inner_eval = apply_risk_boundaries(inner_eval.risk_volatility_next_20d, inner_cutoffs)
        y_outer_train = apply_risk_boundaries(outer_train.risk_volatility_next_20d, outer_cutoffs)
        y_outer_eval = apply_risk_boundaries(outer_eval.risk_volatility_next_20d, outer_cutoffs)
        for labels, expected in (
            (y_inner_train, inner_saved["train_class_counts"]),
            (y_inner_eval, inner_saved["evaluation_class_counts"]),
            (y_outer_train, outer_saved["train_class_counts"]),
            (y_outer_eval, outer_saved["evaluation_class_counts"]),
        ):
            if np.bincount(labels, minlength=3).tolist() != expected:
                raise ValueError("Risk classes differ from frozen fold cutoffs")
        candidates = []
        inner_sets = matched_feature_sets(inner_train, inner_eval, protocol)
        for group, (x_train, x_eval) in inner_sets.items():
            for leaves in grid:
                probabilities = fit_predict(x_train, y_inner_train, x_eval, leaves, fixed)
                candidates.append({
                    "feature_group": group, "features": list(x_train.columns),
                    "max_leaf_nodes": leaves,
                    "inner_macro_f1": float(f1_score(y_inner_eval, probabilities.argmax(axis=1),
                                                     labels=[0, 1, 2], average="macro", zero_division=0)),
                    "inner_probability_metrics": _probability_metrics(y_inner_eval, probabilities),
                })
        # A tie keeps the first candidate in frozen feature-group and grid order.
        selected = max(candidates, key=lambda row: row["inner_macro_f1"])
        x_train, x_eval = matched_feature_sets(outer_train, outer_eval, protocol)[selected["feature_group"]]
        probabilities = fit_predict(x_train, y_outer_train, x_eval, selected["max_leaf_nodes"], fixed)
        prediction = probabilities.argmax(axis=1)
        prior = np.bincount(y_outer_train, minlength=3) / len(y_outer_train)
        prior_class = int(np.argmax(prior))
        trailing_class = apply_risk_boundaries(outer_eval.volatility_20d, outer_cutoffs)
        rows = outer_eval[["ticker", "session_date", "target_window_end",
                           "risk_volatility_next_20d", "volatility_20d"]].copy()
        rows.insert(0, "fold", fold["fold"])
        rows["feature_group"] = selected["feature_group"]
        rows["fold_risk_class"] = y_outer_eval
        rows["p_low"], rows["p_medium"], rows["p_high"] = probabilities.T
        rows["predicted_class"] = prediction
        rows["prior_p_low"], rows["prior_p_medium"], rows["prior_p_high"] = prior
        rows["prior_predicted_class"] = prior_class
        rows["trailing_predicted_class"] = trailing_class
        prediction_parts.append(rows)
        log = {
            "fold": fold["fold"], "inner_risk_boundaries": inner_cutoffs,
            "outer_risk_boundaries": outer_cutoffs,
            "inner_training": _role_log(inner_train, inner_saved),
            "outer_training": _role_log(outer_train, outer_saved),
            "inner_evaluation_rows": len(inner_eval),
            "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
            "outer_evaluation_rows": len(outer_eval),
            "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
            "candidates": candidates, "selected": selected,
            "outer_macro_f1": float(f1_score(y_outer_eval, prediction, labels=[0, 1, 2],
                                             average="macro", zero_division=0)),
            "outer_probability_metrics": _probability_metrics(y_outer_eval, probabilities),
            "outer_prior_macro_f1": float(f1_score(y_outer_eval, np.full(len(y_outer_eval), prior_class),
                                                   labels=[0, 1, 2], average="macro", zero_division=0)),
            "outer_trailing_macro_f1": float(f1_score(y_outer_eval, trailing_class,
                                                      labels=[0, 1, 2], average="macro", zero_division=0)),
        }
        if not log["inner_training"]["matches_protocol"] or not log["outer_training"]["matches_protocol"]:
            raise ValueError("Fitting rows differ from frozen protocol")
        logs.append(log)
    output_rows = pd.concat(prediction_parts, ignore_index=True)
    logistic_prediction_hash = _compare_logistic(output_rows, logistic_dir)
    report = {
        "stage": "phase5_step_5_8", "dataset_sha256": sha256(data_path),
        "protocol_sha256": sha256(protocol_path), "code_sha256": sha256(__file__),
        "feature_selector_sha256": sha256(Path(__file__).with_name("phase5_baselines.py")),
        "tree_helper_sha256": sha256(Path(__file__).with_name("phase5_return_histgbm.py")),
        "risk_metrics_helper_sha256": sha256(Path(__file__).with_name("phase5_risk_logistic.py")),
        "matched_logistic_prediction_sha256": logistic_prediction_hash,
        "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                        "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "model": {"estimator": "HistGradientBoostingClassifier", "fixed": fixed,
                  "max_leaf_nodes_grid": grid},
        "selection_rule": "Maximize inner macro F1; ties keep frozen group/leaf order. Outer outcomes only score.",
        "class_order": ["Low", "Medium", "High"], "folds": logs,
    }
    if output_dir is not None:
        output_dir = Path(output_dir)
        if output_dir.exists():
            raise FileExistsError(output_dir)
        output_dir.mkdir(parents=True)
        path = output_dir / "outer_predictions.csv"
        output_rows.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
        report["prediction_sha256"] = sha256(path)
        report["prediction_rows"] = len(output_rows)
        (output_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report, output_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--logistic-dir", type=Path, default=DEFAULT_LOGISTIC_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result, _ = run(args.data, args.protocol, args.logistic_dir, args.output_dir)
    print(json.dumps({"folds": len(result["folds"]), "output": str(args.output_dir)}))
