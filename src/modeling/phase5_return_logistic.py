"""Phase 5.4: tune return Logistic Regression inside each frozen fold.

Run: python -m src.modeling.phase5_return_logistic --output-dir reports/generated/phase5_return_logistic
"""

import argparse
import json
import platform
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features.build_dataset import sha256
from src.features.market import FEATURE_COLUMNS
from src.modeling.evaluation_protocol import _hash_keys
from src.modeling.phase5_baselines import (
    DEFAULT_DATA, DEFAULT_PROTOCOL, _return_ranking, fold_roles,
    matched_feature_sets, verify_inputs,
)


def _fit_and_predict(x_train, y_train, x_eval, c):
    """Only feature matrices enter the pipeline; targets are explicit fit inputs."""
    if list(x_train.columns) != list(x_eval.columns) or not set(np.unique(y_train)) == {0, 1, 2}:
        raise ValueError("Feature order or training classes are invalid")
    if not x_train.columns.is_unique or set(x_train.columns) - set(FEATURE_COLUMNS):
        raise ValueError("Non-allowlisted model input")
    if x_train.isna().any().any() or x_eval.isna().any().any():
        raise ValueError("Missing model input")
    model = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1000, solver="lbfgs"))
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=ConvergenceWarning)
        model.fit(x_train, y_train)
    classes = model.named_steps["logisticregression"].classes_
    if not np.array_equal(classes, [0, 1, 2]):
        raise ValueError("Unexpected model class order")
    probabilities = model.predict_proba(x_eval)
    if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1):
        raise ValueError("Invalid class probabilities")
    return model, probabilities


def _role_log(rows, saved):
    return {"rows": len(rows), "keys_sha256": _hash_keys(rows),
            "first_session": rows.session_date.min(), "last_session": rows.session_date.max(),
            "last_target_end": rows.target_window_end.max(),
            "matches_protocol": len(rows) == saved["train_rows"] and
            _hash_keys(rows) == saved["train_keys_sha256"]}


def run(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL, output_dir=None):
    frame, _, protocol = verify_inputs(data_path, protocol_path)
    grid = protocol["experiment_protocol"]["search_budget"]["logistic_C"]
    if grid != [0.1, 1.0, 10.0]:
        raise ValueError("Frozen Logistic Regression search grid mismatch")
    reports, predictions = [], []
    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, "return", "inner")
        outer_train, outer_eval = fold_roles(frame, fold, "return", "outer")
        if inner_train.target_window_end.max() >= fold["inner_first"]:
            raise ValueError("Inner training target overlaps validation")
        if inner_eval.target_window_end.max() >= fold["outer_first"]:
            raise ValueError("Inner validation target overlaps outer evaluation")
        if outer_train.target_window_end.max() >= fold["outer_first"]:
            raise ValueError("Outer training target overlaps evaluation")
        inner_sets = matched_feature_sets(inner_train, inner_eval, protocol)
        outer_sets = matched_feature_sets(outer_train, outer_eval, protocol)
        y_inner = inner_train.relative_return_class.astype(int).to_numpy()
        y_outer = outer_train.relative_return_class.astype(int).to_numpy()
        candidates = []
        for group, (x_train, x_eval) in inner_sets.items():
            for c in grid:
                _, probabilities = _fit_and_predict(x_train, y_inner, x_eval, c)
                score = probabilities[:, 2] - probabilities[:, 0]
                ranking = _return_ranking(inner_eval, score)
                if ranking["defined_spearman_dates"] != fold["tasks"]["return"]["inner"]["ranking_dates"]:
                    raise ValueError("Undefined inner ranking date")
                candidates.append({"feature_group": group, "features": list(x_train.columns), "C": c,
                                   "inner_mean_daily_spearman": ranking["mean_daily_spearman"],
                                   "inner_macro_f1": float(f1_score(inner_eval.relative_return_class.astype(int),
                                                                    probabilities.argmax(axis=1), average="macro"))})
        # max() retains the first candidate on a tie: frozen group order, then C order.
        chosen = max(candidates, key=lambda row: row["inner_mean_daily_spearman"])
        x_train, x_eval = outer_sets[chosen["feature_group"]]
        _, probabilities = _fit_and_predict(x_train, y_outer, x_eval, chosen["C"])
        score = probabilities[:, 2] - probabilities[:, 0]
        prior = np.bincount(y_outer, minlength=3) / len(y_outer)
        rows = outer_eval[["ticker", "session_date", "target_window_end", "relative_return_class",
                           "return_next_20d", "momentum_20d"]].copy()
        rows.insert(0, "fold", fold["fold"])
        rows["feature_group"] = chosen["feature_group"]
        rows["p_lower"], rows["p_middle"], rows["p_higher"] = probabilities.T
        rows["rank_score"] = score
        rows["predicted_class"] = probabilities.argmax(axis=1)
        rows["prior_p_lower"], rows["prior_p_middle"], rows["prior_p_higher"] = prior
        rows["prior_predicted_class"] = int(np.argmax(prior))
        predictions.append(rows)
        inner_saved = fold["tasks"]["return"]["inner"]
        outer_saved = fold["tasks"]["return"]["outer"]
        log = {"fold": fold["fold"], "inner_training": _role_log(inner_train, inner_saved),
               "outer_training": _role_log(outer_train, outer_saved),
               "inner_evaluation_rows": len(inner_eval), "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
               "outer_evaluation_rows": len(outer_eval), "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
               "candidates": candidates, "selected": chosen,
               "outer_prior_macro_f1": float(f1_score(outer_eval.relative_return_class.astype(int),
                                                       np.full(len(outer_eval), int(np.argmax(prior))), average="macro")),
               "outer_momentum_mean_daily_spearman": _return_ranking(
                   outer_eval, outer_eval.momentum_20d)["mean_daily_spearman"],
               "outer_macro_f1": float(f1_score(outer_eval.relative_return_class.astype(int),
                                                probabilities.argmax(axis=1), average="macro")),
               "outer_mean_daily_spearman": _return_ranking(outer_eval, score)["mean_daily_spearman"]}
        if not log["inner_training"]["matches_protocol"] or not log["outer_training"]["matches_protocol"]:
            raise ValueError("Fitting role differs from frozen protocol")
        reports.append(log)
    prediction_frame = pd.concat(predictions, ignore_index=True)
    report = {"stage": "phase5_step_5_4", "dataset_sha256": sha256(data_path),
              "protocol_sha256": sha256(protocol_path), "code_sha256": sha256(__file__),
              "feature_selector_sha256": sha256(Path(__file__).with_name("phase5_baselines.py")),
              "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                              "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "model": {"estimator": "LogisticRegression", "solver": "lbfgs", "max_iter": 1000,
                        "preprocessing": "StandardScaler fit on training rows only", "C_grid": grid},
              "selection_rule": "Maximize mean within-date Spearman on inner validation only; ties keep frozen group/C order.",
              "rank_score_meaning": "P(Higher)-P(Lower), not percentage return",
              "folds": reports}
    if output_dir is not None:
        output_dir = Path(output_dir)
        if output_dir.exists():
            raise FileExistsError(output_dir)
        output_dir.mkdir(parents=True)
        prediction_path = output_dir / "outer_predictions.csv"
        prediction_frame.to_csv(prediction_path, index=False, lineterminator="\n", float_format="%.17g")
        report["prediction_sha256"] = sha256(prediction_path)
        report["prediction_rows"] = len(prediction_frame)
        (output_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report, prediction_frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, _ = run(args.data, args.protocol, args.output_dir)
    print(json.dumps({"folds": len(report["folds"]), "output": str(args.output_dir)}))
