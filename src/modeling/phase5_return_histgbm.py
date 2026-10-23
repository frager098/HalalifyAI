"""Phase 5.5 return HistGradientBoosting on frozen chronological folds."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score

from src.features.build_dataset import sha256
from src.features.market import FEATURE_COLUMNS
from src.modeling.evaluation_protocol import _hash_keys
from src.modeling.phase5_baselines import (DEFAULT_DATA, DEFAULT_PROTOCOL,
    _return_ranking, fold_roles, matched_feature_sets, verify_inputs)
from src.modeling.phase5_return_logistic import _role_log


def fit_predict(x_train, y_train, x_eval, leaves, fixed):
    """Fit only on explicit training features and return the 0/1/2 probabilities."""
    if list(x_train.columns) != list(x_eval.columns) or not x_train.columns.is_unique:
        raise ValueError("Feature order mismatch")
    if set(x_train.columns) - set(FEATURE_COLUMNS):
        raise ValueError("Non-allowlisted model input")
    if set(np.unique(y_train)) != {0, 1, 2} or len(y_train) != len(x_train):
        raise ValueError("Invalid training target")
    if x_train.isna().any().any() or x_eval.isna().any().any():
        raise ValueError("Missing model input")
    model = HistGradientBoostingClassifier(max_leaf_nodes=leaves, **fixed)
    model.fit(x_train, y_train)
    if not np.array_equal(model.classes_, [0, 1, 2]):
        raise ValueError("Unexpected class order")
    probabilities = model.predict_proba(x_eval)
    if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1):
        raise ValueError("Invalid class probabilities")
    return probabilities


def run(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL, output_dir=None):
    frame, _, protocol = verify_inputs(data_path, protocol_path)
    budget = protocol["experiment_protocol"]["search_budget"]
    leaves_grid, fixed = budget["hist_gbm_max_leaf_nodes"], budget["hist_gbm_fixed"]
    if leaves_grid != [15, 31, 63] or fixed != {"max_iter": 100, "learning_rate": 0.1,
                                                "early_stopping": False, "random_state": 42}:
        raise ValueError("Frozen boosted-tree settings mismatch")
    logs, predictions = [], []
    for fold in protocol["folds"]:
        inner_train, inner_eval = fold_roles(frame, fold, "return", "inner")
        outer_train, outer_eval = fold_roles(frame, fold, "return", "outer")
        if (inner_train.target_window_end.max() >= fold["inner_first"] or
                inner_eval.target_window_end.max() >= fold["outer_first"] or
                outer_train.target_window_end.max() >= fold["outer_first"]):
            raise ValueError("Outcome window overlaps evaluation boundary")
        inner_sets = matched_feature_sets(inner_train, inner_eval, protocol)
        outer_sets = matched_feature_sets(outer_train, outer_eval, protocol)
        candidates = []
        for group, (x_train, x_eval) in inner_sets.items():
            for leaves in leaves_grid:
                probabilities = fit_predict(x_train, inner_train.relative_return_class.to_numpy(dtype=int),
                                            x_eval, leaves, fixed)
                ranking = _return_ranking(inner_eval, probabilities[:, 2] - probabilities[:, 0])
                if ranking["defined_spearman_dates"] != fold["tasks"]["return"]["inner"]["ranking_dates"]:
                    raise ValueError("Undefined inner ranking date")
                candidates.append({"feature_group": group, "features": list(x_train.columns),
                                   "max_leaf_nodes": leaves,
                                   "inner_mean_daily_spearman": ranking["mean_daily_spearman"],
                                   "inner_macro_f1": float(f1_score(inner_eval.relative_return_class.astype(int),
                                                                    probabilities.argmax(axis=1), average="macro"))})
        selected = max(candidates, key=lambda row: row["inner_mean_daily_spearman"])
        x_train, x_eval = outer_sets[selected["feature_group"]]
        probabilities = fit_predict(x_train, outer_train.relative_return_class.to_numpy(dtype=int),
                                    x_eval, selected["max_leaf_nodes"], fixed)
        score = probabilities[:, 2] - probabilities[:, 0]
        prior = np.bincount(outer_train.relative_return_class.to_numpy(dtype=int), minlength=3) / len(outer_train)
        rows = outer_eval[["ticker", "session_date", "target_window_end", "relative_return_class",
                           "return_next_20d", "momentum_20d"]].copy()
        rows.insert(0, "fold", fold["fold"])
        rows["feature_group"] = selected["feature_group"]
        rows["p_lower"], rows["p_middle"], rows["p_higher"] = probabilities.T
        rows["rank_score"] = score
        rows["predicted_class"] = probabilities.argmax(axis=1)
        rows["prior_p_lower"], rows["prior_p_middle"], rows["prior_p_higher"] = prior
        rows["prior_predicted_class"] = int(np.argmax(prior))
        predictions.append(rows)
        inner_saved, outer_saved = (fold["tasks"]["return"][role] for role in ("inner", "outer"))
        log = {"fold": fold["fold"], "inner_training": _role_log(inner_train, inner_saved),
               "outer_training": _role_log(outer_train, outer_saved),
               "inner_evaluation_keys_sha256": _hash_keys(inner_eval),
               "outer_evaluation_keys_sha256": _hash_keys(outer_eval),
               "outer_evaluation_rows": len(outer_eval), "candidates": candidates, "selected": selected,
               "outer_mean_daily_spearman": _return_ranking(outer_eval, score)["mean_daily_spearman"],
               "outer_momentum_mean_daily_spearman": _return_ranking(
                   outer_eval, outer_eval.momentum_20d)["mean_daily_spearman"],
               "outer_macro_f1": float(f1_score(outer_eval.relative_return_class.astype(int),
                                                probabilities.argmax(axis=1), average="macro"))}
        if not log["inner_training"]["matches_protocol"] or not log["outer_training"]["matches_protocol"]:
            raise ValueError("Fitting rows differ from frozen protocol")
        logs.append(log)
    output_rows = pd.concat(predictions, ignore_index=True)
    report = {"stage": "phase5_step_5_5", "dataset_sha256": sha256(data_path),
              "protocol_sha256": sha256(protocol_path), "code_sha256": sha256(__file__),
              "feature_selector_sha256": sha256(Path(__file__).with_name("phase5_baselines.py")),
              "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                              "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "model": {"estimator": "HistGradientBoostingClassifier", "fixed": fixed,
                        "max_leaf_nodes_grid": leaves_grid},
              "selection_rule": "Maximize inner mean same-date Spearman; ties keep frozen group/grid order.",
              "rank_score_meaning": "P(Higher)-P(Lower), not percentage return", "folds": logs}
    if output_dir is not None:
        output_dir = Path(output_dir)
        if output_dir.exists():
            raise FileExistsError(output_dir)
        output_dir.mkdir(parents=True)
        prediction_path = output_dir / "outer_predictions.csv"
        output_rows.to_csv(prediction_path, index=False, lineterminator="\n", float_format="%.17g")
        report["prediction_sha256"] = sha256(prediction_path)
        report["prediction_rows"] = len(output_rows)
        (output_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report, output_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, _ = run(args.data, args.protocol, args.output_dir)
    print(json.dumps({"folds": len(report["folds"]), "output": str(args.output_dir)}))
