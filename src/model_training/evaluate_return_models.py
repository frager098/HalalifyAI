"""Review matched Phase 5 return predictions without fitting or retuning."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.chronological_evaluation_protocol import _hash_keys
from src.model_training.baseline_models import DEFAULT_PROTOCOL, FROZEN_DATA_SHA256, FROZEN_PROTOCOL_SHA256

DEFAULT_LOGISTIC = Path("reports/generated/current/return_logistic_classifier")
DEFAULT_TREE = Path("reports/generated/current/return_gradient_boosting_classifier")


def _read_model(directory, stage, code_file):
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    path = directory / "outer_predictions.csv"
    if report["stage"] != stage or report["dataset_sha256"] != FROZEN_DATA_SHA256 or report["protocol_sha256"] != FROZEN_PROTOCOL_SHA256:
        raise ValueError(f"{stage}: input versions differ")
    if report["code_sha256"] != sha256(code_file) or report["prediction_sha256"] != sha256(path):
        raise ValueError(f"{stage}: code or prediction checksum differs")
    rows = pd.read_csv(path)
    if len(rows) != report["prediction_rows"] or rows.duplicated(["fold", "ticker", "session_date"]).any():
        raise ValueError(f"{stage}: prediction rows are invalid")
    probabilities = rows[["p_lower", "p_middle", "p_higher"]].to_numpy()
    if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1):
        raise ValueError(f"{stage}: invalid probabilities")
    if not np.allclose(probabilities[:, 2] - probabilities[:, 0], rows.rank_score):
        raise ValueError(f"{stage}: rank score differs from probabilities")
    return report, rows


def _class_metrics(truth, prediction):
    labels = [0, 1, 2]
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, prediction, labels=labels, zero_division=0)
    return {"macro_f1": float(f1_score(truth, prediction, labels=labels, average="macro", zero_division=0)),
            "ordinal_mae": float(np.mean(np.abs(np.asarray(truth) - np.asarray(prediction)))),
            "confusion_matrix": confusion_matrix(truth, prediction, labels=labels).tolist(),
            "per_class": {name: {"precision": float(precision[i]), "recall": float(recall[i]),
                                 "f1": float(f1[i]), "support": int(support[i])}
                          for i, name in enumerate(("Lower", "Middle", "Higher"))}}


def _date_metrics(rows):
    daily = []
    for date, group in rows.groupby("session_date", sort=True):
        if not 45 <= len(group) <= 50 or group.ticker.nunique() != len(group):
            raise ValueError("Invalid same-date peer group")
        score = group.rank_score
        outcome = group.return_next_20d
        ic = None if score.nunique() < 2 or outcome.nunique() < 2 else float(spearmanr(score, outcome).statistic)
        top = group.sort_values(["rank_score", "ticker"], ascending=[False, True], kind="stable").head(10)
        daily.append({"date": date, "peers": len(group), "spearman": ic,
                      "top10_minus_universe": float(top.return_next_20d.mean() - outcome.mean())})
    defined = [row["spearman"] for row in daily if row["spearman"] is not None]
    return {"dates": len(daily), "defined_spearman_dates": len(defined),
            "mean_daily_spearman": float(np.mean(defined)) if defined else None,
            "mean_top10_minus_universe": float(np.mean([row["top10_minus_universe"] for row in daily])),
            "daily": daily}


def review(logistic_dir=DEFAULT_LOGISTIC, tree_dir=DEFAULT_TREE, protocol_path=DEFAULT_PROTOCOL, output=None):
    if sha256(protocol_path) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Frozen protocol checksum differs")
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    logistic_report, logistic = _read_model(Path(logistic_dir), "phase5_step_5_4", "src/model_training/return_logistic_classifier.py")
    tree_report, tree = _read_model(Path(tree_dir), "phase5_step_5_5", "src/model_training/return_gradient_boosting_classifier.py")
    keys = ["fold", "ticker", "session_date"]
    if not logistic[keys].equals(tree[keys]):
        raise ValueError("Model prediction cohorts differ")
    shared = ["target_window_end", "relative_return_class", "return_next_20d", "momentum_20d",
              "prior_p_lower", "prior_p_middle", "prior_p_higher", "prior_predicted_class"]
    if not logistic[shared].equals(tree[shared]):
        raise ValueError("Model target or baseline rows differ")
    folds = []
    for fold in protocol["folds"]:
        number = fold["fold"]
        mask = logistic.fold.eq(number)
        saved = fold["tasks"]["return"]["outer"]
        if (int(mask.sum()) != saved["evaluation_rows"] or
                _hash_keys(logistic.loc[mask]) != saved["evaluation_keys_sha256"] or
                logistic.loc[mask, "session_date"].max() >= protocol["test_start"]):
            raise ValueError("Unexpected outer evaluation rows")
        methods = {}
        for name, source in (("LogisticRegression", logistic), ("HistGradientBoosting", tree)):
            rows = source.loc[mask]
            methods[name] = {"ranking": _date_metrics(rows),
                             "classification": _class_metrics(rows.relative_return_class.astype(int),
                                                                  rows.predicted_class.astype(int))}
        prior_rows = logistic.loc[mask]
        methods["training_class_prior"] = {"ranking": {"mean_daily_spearman": None,
                                                         "reason": "Constant within each date; no stock ordering"},
                                           "classification": _class_metrics(prior_rows.relative_return_class.astype(int),
                                                                            prior_rows.prior_predicted_class.astype(int))}
        momentum = prior_rows.copy()
        momentum["rank_score"] = momentum.momentum_20d
        methods["momentum_20d"] = {"ranking": _date_metrics(momentum)}
        folds.append({"fold": number, "evaluation_rows": int(mask.sum()), "methods": methods})
    names = ["LogisticRegression", "HistGradientBoosting", "momentum_20d"]
    mean_spearman = {name: float(np.mean([fold["methods"][name]["ranking"]["mean_daily_spearman"]
                                            for fold in folds])) for name in names}
    mean_spread = {name: float(np.mean([fold["methods"][name]["ranking"]["mean_top10_minus_universe"]
                                          for fold in folds])) for name in names}
    paired = {}
    for name in ("LogisticRegression", "HistGradientBoosting"):
        ic_differences, spread_differences = [], []
        for fold in folds:
            model_days = fold["methods"][name]["ranking"]["daily"]
            benchmark_days = fold["methods"]["momentum_20d"]["ranking"]["daily"]
            if [day["date"] for day in model_days] != [day["date"] for day in benchmark_days]:
                raise ValueError("Ranking dates differ from momentum")
            for model_day, benchmark_day in zip(model_days, benchmark_days):
                if model_day["spearman"] is not None and benchmark_day["spearman"] is not None:
                    ic_differences.append(model_day["spearman"] - benchmark_day["spearman"])
                spread_differences.append(model_day["top10_minus_universe"] -
                                          benchmark_day["top10_minus_universe"])
        paired[name] = {"dates": len(spread_differences),
                        "mean_daily_ic_difference": float(np.mean(ic_differences)),
                        "mean_top10_spread_difference": float(np.mean(spread_differences)),
                        "top10_dates_above_momentum": int(np.sum(np.asarray(spread_differences) > 0)),
                        "folds_with_higher_ic": sum(
                            fold["methods"][name]["ranking"]["mean_daily_spearman"] >
                            fold["methods"]["momentum_20d"]["ranking"]["mean_daily_spearman"]
                            for fold in folds)}
    report = {"stage": "phase5_step_5_6", "dataset_sha256": FROZEN_DATA_SHA256,
              "protocol_sha256": FROZEN_PROTOCOL_SHA256,
              "logistic_prediction_sha256": logistic_report["prediction_sha256"],
              "tree_prediction_sha256": tree_report["prediction_sha256"],
              "mean_fold_spearman": mean_spearman, "mean_fold_top10_minus_universe": mean_spread,
              "paired_vs_momentum": paired,
              "decision": "Select no return approach. Keep trailing 20-day momentum only as a simple benchmark/control; its mean outer Spearman is effectively zero and it is not an endorsed effective strategy.",
              "class_order": ["Lower", "Middle", "Higher"],
              "interpretation": "Top-10 uses known-close forward returns; research selection diagnostic, not executable performance.",
              "folds": folds}
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
    result = review(output=args.output)
    print(json.dumps({"folds": len(result["folds"]), "output": str(args.output)}))
