"""Phase 5.9: review matched risk errors without fitting or retuning.

Run: python -m src.modeling.phase5_risk_review --output reports/generated/phase5_risk_review.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_recall_fscore_support, r2_score)

from src.features.build_dataset import sha256
from src.modeling.evaluation_protocol import _hash_keys, apply_risk_boundaries
from src.modeling.phase5_baselines import (DEFAULT_PROTOCOL, FROZEN_DATA_SHA256,
                                           FROZEN_PROTOCOL_SHA256)
from src.modeling.phase5_risk_logistic import _probability_metrics

DEFAULT_LOGISTIC = Path("reports/generated/phase5_risk_logistic")
DEFAULT_TREE = Path("reports/generated/phase5_risk_histgbm")
CLASS_NAMES = ("Low", "Medium", "High")


def _read_model(directory, stage, code_path):
    directory = Path(directory)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    path = directory / "outer_predictions.csv"
    if (report["stage"] != stage or report["dataset_sha256"] != FROZEN_DATA_SHA256 or
            report["protocol_sha256"] != FROZEN_PROTOCOL_SHA256 or
            report["code_sha256"] != sha256(code_path) or
            report["prediction_sha256"] != sha256(path)):
        raise ValueError(f"{stage}: source or prediction version mismatch")
    helpers = {
        "feature_selector_sha256": "src/modeling/phase5_baselines.py",
        "logistic_helper_sha256": "src/modeling/phase5_return_logistic.py",
        "tree_helper_sha256": "src/modeling/phase5_return_histgbm.py",
        "risk_metrics_helper_sha256": "src/modeling/phase5_risk_logistic.py",
    }
    for field, helper_path in helpers.items():
        if field in report and report[field] != sha256(helper_path):
            raise ValueError(f"{stage}: {field} differs from saved version")
    rows = pd.read_csv(path)
    if len(rows) != report["prediction_rows"] or rows.duplicated(["fold", "ticker", "session_date"]).any():
        raise ValueError(f"{stage}: invalid prediction keys")
    probabilities = rows[["p_low", "p_medium", "p_high"]].to_numpy()
    if (not np.isfinite(probabilities).all() or
            (probabilities < 0).any() or (probabilities > 1).any() or
            not np.allclose(probabilities.sum(axis=1), 1, atol=1e-12) or
            not np.array_equal(probabilities.argmax(axis=1), rows.predicted_class.to_numpy())):
        raise ValueError(f"{stage}: invalid probabilities or class order")
    return report, rows


def _class_metrics(truth, prediction):
    truth = np.asarray(truth, dtype=int)
    prediction = np.asarray(prediction, dtype=int)
    if not np.isin(truth, [0, 1, 2]).all() or not np.isin(prediction, [0, 1, 2]).all():
        raise ValueError("Invalid risk class")
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, prediction, labels=[0, 1, 2], zero_division=0)
    return {
        "macro_f1": float(f1_score(truth, prediction, labels=[0, 1, 2],
                                   average="macro", zero_division=0)),
        "ordinal_mae": float(np.mean(np.abs(truth - prediction))),
        "high_predicted_low_count": int(((truth == 2) & (prediction == 0)).sum()),
        "high_predicted_low_rate_among_high": float(((truth == 2) & (prediction == 0)).sum() /
                                                     max((truth == 2).sum(), 1)),
        "confusion_matrix": confusion_matrix(truth, prediction, labels=[0, 1, 2]).tolist(),
        "per_class": {name: {"precision": float(precision[i]), "recall": float(recall[i]),
                             "f1": float(f1[i]), "support": int(support[i])}
                      for i, name in enumerate(CLASS_NAMES)},
    }


def review(logistic_dir=DEFAULT_LOGISTIC, tree_dir=DEFAULT_TREE,
           protocol_path=DEFAULT_PROTOCOL, output=None):
    if sha256(protocol_path) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Frozen protocol checksum mismatch")
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    logistic_report, logistic = _read_model(logistic_dir, "phase5_step_5_7",
                                            "src/modeling/phase5_risk_logistic.py")
    tree_report, tree = _read_model(tree_dir, "phase5_step_5_8",
                                    "src/modeling/phase5_risk_histgbm.py")
    if tree_report["matched_logistic_prediction_sha256"] != logistic_report["prediction_sha256"]:
        raise ValueError("Tree was compared with a different Logistic Regression run")
    exact = ["fold", "ticker", "session_date", "target_window_end",
             "fold_risk_class", "prior_predicted_class"]
    numeric = ["risk_volatility_next_20d", "prior_p_low", "prior_p_medium", "prior_p_high"]
    if (not logistic[exact].equals(tree[exact]) or
            not np.allclose(logistic[numeric], tree[numeric], rtol=0, atol=1e-12)):
        raise ValueError("Risk model rows, targets, or priors differ")
    fold_reports = []
    for fold in protocol["folds"]:
        number = fold["fold"]
        mask = tree.fold.eq(number)
        saved = fold["tasks"]["risk"]["outer"]
        tree_log = tree_report["folds"][number - 1]
        logistic_log = logistic_report["folds"][number - 1]
        if (int(mask.sum()) != saved["evaluation_rows"] or
                _hash_keys(tree.loc[mask]) != saved["evaluation_keys_sha256"] or
                tree.loc[mask, "session_date"].max() >= protocol["test_start"] or
                tree_log["outer_risk_boundaries"] != saved["risk_boundaries"] or
                logistic_log["outer_risk_boundaries"] != saved["risk_boundaries"]):
            raise ValueError("Risk evaluation fold or cutoff differs from protocol")
        tree_rows, logistic_rows = tree.loc[mask], logistic.loc[mask]
        truth = apply_risk_boundaries(tree_rows.risk_volatility_next_20d,
                                      saved["risk_boundaries"])
        if (not np.array_equal(truth, tree_rows.fold_risk_class.to_numpy()) or
                np.bincount(truth, minlength=3).tolist() != saved["evaluation_class_counts"]):
            raise ValueError("Saved risk labels differ from frozen cutoffs")
        prior_probabilities = tree_rows[["prior_p_low", "prior_p_medium", "prior_p_high"]].to_numpy()
        expected_prior = np.asarray(saved["train_class_counts"], dtype=float) / saved["train_rows"]
        if (not np.isfinite(prior_probabilities).all() or
                not np.allclose(prior_probabilities.sum(axis=1), 1) or
                not np.allclose(prior_probabilities, expected_prior, rtol=0, atol=1e-12) or
                not tree_rows.prior_predicted_class.eq(int(np.argmax(expected_prior))).all()):
            raise ValueError("Training-class prior differs within the fold")
        trailing_prediction = apply_risk_boundaries(tree_rows.volatility_20d,
                                                    saved["risk_boundaries"])
        if not np.array_equal(trailing_prediction, tree_rows.trailing_predicted_class.to_numpy()):
            raise ValueError("Trailing baseline differs from frozen cutoffs")
        methods = {}
        for name, rows in (("LogisticRegression", logistic_rows),
                           ("HistGradientBoosting", tree_rows)):
            probabilities = rows[["p_low", "p_medium", "p_high"]].to_numpy()
            methods[name] = {"classification": _class_metrics(truth, rows.predicted_class),
                             "probability": _probability_metrics(truth, probabilities)}
        methods["training_class_prior"] = {
            "classification": _class_metrics(truth, tree_rows.prior_predicted_class),
            "probability": _probability_metrics(truth, prior_probabilities),
        }
        methods["trailing_volatility_20d"] = {
            "classification": _class_metrics(truth, trailing_prediction),
            "numerical_volatility": {
                "mae": float(mean_absolute_error(tree_rows.risk_volatility_next_20d,
                                                 tree_rows.volatility_20d)),
                "rmse": float(np.sqrt(mean_squared_error(tree_rows.risk_volatility_next_20d,
                                                         tree_rows.volatility_20d))),
                "r2": float(r2_score(tree_rows.risk_volatility_next_20d,
                                     tree_rows.volatility_20d)),
            },
        }
        fold_reports.append({"fold": number, "evaluation_rows": int(mask.sum()),
                             "risk_boundaries": saved["risk_boundaries"], "methods": methods})
    names = ["LogisticRegression", "HistGradientBoosting", "training_class_prior",
             "trailing_volatility_20d"]
    summary = {}
    for name in names:
        parts = [fold["methods"][name] for fold in fold_reports]
        summary[name] = {
            "mean_fold_macro_f1": float(np.mean([part["classification"]["macro_f1"] for part in parts])),
            "mean_fold_high_recall": float(np.mean([part["classification"]["per_class"]["High"]["recall"]
                                               for part in parts])),
            "total_high_predicted_low": int(sum(part["classification"]["high_predicted_low_count"]
                                                for part in parts)),
            "total_high_outcomes": int(sum(part["classification"]["per_class"]["High"]["support"]
                                           for part in parts)),
            "mean_fold_ordinal_mae": float(np.mean([part["classification"]["ordinal_mae"] for part in parts])),
        }
        summary[name]["pooled_high_predicted_low_rate"] = (
            summary[name]["total_high_predicted_low"] / summary[name]["total_high_outcomes"])
        if "probability" in parts[0]:
            summary[name]["mean_fold_log_loss"] = float(np.mean(
                [part["probability"]["log_loss"] for part in parts]))
            summary[name]["mean_fold_multiclass_brier"] = float(np.mean(
                [part["probability"]["multiclass_brier"] for part in parts]))
        if name == "trailing_volatility_20d":
            for key in ("mae", "rmse", "r2"):
                summary[name]["mean_fold_" + key] = float(np.mean(
                    [part["numerical_volatility"][key] for part in parts]))
    report = {
        "stage": "phase5_step_5_9", "dataset_sha256": FROZEN_DATA_SHA256,
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "code_sha256": sha256(__file__),
        "logistic_prediction_sha256": logistic_report["prediction_sha256"],
        "tree_prediction_sha256": tree_report["prediction_sha256"],
        "class_order": list(CLASS_NAMES), "summary": summary, "folds": fold_reports,
        "interpretation": "Numerical volatility errors apply to trailing volatility only; classifiers produce risk classes and probabilities.",
    }
    if output is not None:
        output = Path(output)
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review(output=args.output)
    print(json.dumps({"folds": len(report["folds"]), "output": str(args.output)}))
