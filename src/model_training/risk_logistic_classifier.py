"""Phase 5.7: risk Logistic Regression with fold-specific training cutoffs."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import f1_score, log_loss

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.chronological_evaluation_protocol import _hash_keys, apply_risk_boundaries
from src.model_training.baseline_models import (DEFAULT_DATA, DEFAULT_PROTOCOL,
    fold_roles, matched_feature_sets, verify_inputs)
from src.model_training.return_logistic_classifier import _fit_and_predict, _role_log


def _probability_metrics(truth, probabilities):
    truth = np.asarray(truth, dtype=int)
    observed = np.eye(3)[truth]
    return {"log_loss": float(log_loss(truth, probabilities, labels=[0, 1, 2])),
            "multiclass_brier": float(np.mean(np.sum((probabilities - observed) ** 2, axis=1)))}


def run(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL, output_dir=None):
    frame, _, protocol = verify_inputs(data_path, protocol_path)
    grid = protocol["experiment_protocol"]["search_budget"]["logistic_C"]
    if grid != [0.1, 1.0, 10.0]:
        raise ValueError("Frozen Logistic Regression grid mismatch")
    logs, predictions = [], []
    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, "risk", "inner")
        outer_train, outer_eval = fold_roles(frame, fold, "risk", "outer")
        if (inner_train.target_window_end.max() >= fold["inner_first"] or
                inner_eval.target_window_end.max() >= fold["outer_first"] or
                outer_train.target_window_end.max() >= fold["outer_first"]):
            raise ValueError("Risk outcome window overlaps evaluation")
        inner_saved, outer_saved = (fold["tasks"]["risk"][role] for role in ("inner", "outer"))
        inner_cutoffs, outer_cutoffs = inner_saved["risk_boundaries"], outer_saved["risk_boundaries"]
        y_inner_train = apply_risk_boundaries(inner_train.risk_volatility_next_20d, inner_cutoffs)
        y_inner_eval = apply_risk_boundaries(inner_eval.risk_volatility_next_20d, inner_cutoffs)
        y_outer_train = apply_risk_boundaries(outer_train.risk_volatility_next_20d, outer_cutoffs)
        y_outer_eval = apply_risk_boundaries(outer_eval.risk_volatility_next_20d, outer_cutoffs)
        if (np.bincount(y_inner_train, minlength=3).tolist() != inner_saved["train_class_counts"] or
                np.bincount(y_inner_eval, minlength=3).tolist() != inner_saved["evaluation_class_counts"] or
                np.bincount(y_outer_train, minlength=3).tolist() != outer_saved["train_class_counts"] or
                np.bincount(y_outer_eval, minlength=3).tolist() != outer_saved["evaluation_class_counts"]):
            raise ValueError("Risk classes differ from frozen fold cutoffs")
        candidates = []
        for group, (x_train, x_eval) in matched_feature_sets(inner_train, inner_eval, protocol).items():
            for c in grid:
                _, probabilities = _fit_and_predict(x_train, y_inner_train, x_eval, c)
                prediction = probabilities.argmax(axis=1)
                candidates.append({"feature_group": group, "features": list(x_train.columns), "C": c,
                                   "inner_macro_f1": float(f1_score(y_inner_eval, prediction, average="macro")),
                                   "inner_probability_metrics": _probability_metrics(y_inner_eval, probabilities)})
        # The first candidate wins a tie: frozen feature-group order, then C order.
        selected = max(candidates, key=lambda row: row["inner_macro_f1"])
        x_train, x_eval = matched_feature_sets(outer_train, outer_eval, protocol)[selected["feature_group"]]
        _, probabilities = _fit_and_predict(x_train, y_outer_train, x_eval, selected["C"])
        prior = np.bincount(y_outer_train, minlength=3) / len(y_outer_train)
        prior_probabilities = np.broadcast_to(prior, probabilities.shape)
        rows = outer_eval[["ticker", "session_date", "target_window_end", "risk_volatility_next_20d"]].copy()
        rows.insert(0, "fold", fold["fold"])
        rows["feature_group"] = selected["feature_group"]
        rows["fold_risk_class"] = y_outer_eval
        rows["p_low"], rows["p_medium"], rows["p_high"] = probabilities.T
        rows["predicted_class"] = probabilities.argmax(axis=1)
        rows["prior_p_low"], rows["prior_p_medium"], rows["prior_p_high"] = prior
        rows["prior_predicted_class"] = int(np.argmax(prior))
        predictions.append(rows)
        log = {"fold": fold["fold"], "inner_risk_boundaries": inner_cutoffs,
               "outer_risk_boundaries": outer_cutoffs,
               "inner_training": _role_log(inner_train, inner_saved),
               "outer_training": _role_log(outer_train, outer_saved),
               "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
               "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
               "outer_evaluation_rows": len(outer_eval),
               "candidates": candidates, "selected": selected,
               "outer_macro_f1": float(f1_score(y_outer_eval, probabilities.argmax(axis=1), average="macro")),
               "outer_probability_metrics": _probability_metrics(y_outer_eval, probabilities),
               "outer_prior_macro_f1": float(f1_score(y_outer_eval,
                                                       np.full(len(y_outer_eval), int(np.argmax(prior))),
                                                       average="macro")),
               "outer_prior_probability_metrics": _probability_metrics(y_outer_eval, prior_probabilities)}
        if not log["inner_training"]["matches_protocol"] or not log["outer_training"]["matches_protocol"]:
            raise ValueError("Risk fitting rows differ from frozen protocol")
        logs.append(log)
    output_rows = pd.concat(predictions, ignore_index=True)
    report = {"stage": "phase5_step_5_7", "dataset_sha256": sha256(data_path),
              "protocol_sha256": sha256(protocol_path), "code_sha256": sha256(__file__),
              "feature_selector_sha256": sha256(Path(__file__).with_name("baseline_models.py")),
              "logistic_helper_sha256": sha256(Path(__file__).with_name("return_logistic_classifier.py")),
              "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                              "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "model": {"estimator": "LogisticRegression", "solver": "lbfgs", "max_iter": 1000,
                        "preprocessing": "StandardScaler fit on training rows only", "C_grid": grid},
              "selection_rule": "Maximize inner macro F1; ties keep frozen group/C order. Outer outcomes only score.",
              "class_order": ["Low", "Medium", "High"], "folds": logs}
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
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result, _ = run(args.data, args.protocol, args.output_dir)
    print(json.dumps({"folds": len(result["folds"]), "output": str(args.output_dir)}))
