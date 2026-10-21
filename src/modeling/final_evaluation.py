"""Freeze a development choice, then run one explicitly reused-test check.

Commands:
  python -m src.modeling.final_evaluation freeze
  python -m src.modeling.final_evaluation evaluate --protocol PATH

The 2024-2025 test scores were previously exposed in baseline notebooks.
This check is not a fresh blind final estimate.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import classification_report, mean_absolute_error, mean_squared_error, r2_score

from src.features.market import build_market_features
from src.modeling.compare_features import DEFAULT_DATA, ROOT
from src.modeling.walk_forward import (CLASSES, FEATURE_GROUPS, TOP_N, classes,
                                       estimator, feature_sets, rank_metrics,
                                       rebalance_dates, thresholds)


DEVELOPMENT = ROOT / "reports/generated/walk_forward_20261020T105443Z"
FEATURE_CODE = ROOT / "src/features/market.py"
MODEL_CODE = ROOT / "src/modeling/walk_forward.py"
THIS_CODE = Path(__file__).resolve()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def frozen_protocol(data_path=DEFAULT_DATA, development_dir=DEVELOPMENT):
    data_path = Path(data_path)
    development_dir = Path(development_dir)
    metadata_path = data_path.with_name("targets_metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if digest(data_path) != metadata["output_sha256"]:
        raise ValueError("Model dataset checksum mismatch")
    development = json.loads((development_dir / "manifest.json").read_text(encoding="utf-8"))
    if development["dataset_sha256"] != metadata["output_sha256"]:
        raise ValueError("Development results used a different dataset")
    columns = feature_sets()["03_market_relative"]
    if columns != development["feature_sets"]["03_market_relative"]:
        raise ValueError("Frozen feature columns differ from development run")
    return {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "predeclared_reused_test_check_not_blind",
        "selection_source": str(development_dir),
        "selection_rule": "Risk: use simple Ridge with groups 1-3; volume had no clear gain. Return: retain momentum; best learned challenger failed to beat it across folds.",
        "dataset": str(data_path.resolve()),
        "dataset_sha256": digest(data_path),
        "target_metadata_sha256": digest(metadata_path),
        "development_manifest_sha256": digest(development_dir / "manifest.json"),
        "development_risk_summary_sha256": digest(development_dir / "risk_summary.csv"),
        "development_return_comparison_sha256": digest(development_dir / "return_vs_momentum_summary.csv"),
        "code_sha256": {"final_evaluation.py": digest(THIS_CODE),
                        "walk_forward.py": digest(MODEL_CODE),
                        "market.py": digest(FEATURE_CODE)},
        "library_versions": {"pandas": pd.__version__, "numpy": np.__version__,
                             "scikit_learn": sklearn.__version__},
        "training_rule": "All rows before test_start whose 20-session target ends before test_start; common factor-ready cohort; fit thresholds and preprocessing on these rows only.",
        "evaluation_rule": "Saved dataset_split=test rows, with complete 20-session targets and common factor-ready inputs. No parameter change after freeze.",
        "test_start": metadata["test_start"],
        "risk_model": {"name": "ridge", "feature_columns": columns, "alpha": 100.0},
        "risk_baseline": "trailing_volatility_20d",
        "return_choice": "momentum_20d",
        "return_challenger": {"name": "hist_gbm", "feature_columns": columns,
                              "max_iter": 50, "max_leaf_nodes": 15,
                              "l2_regularization": 1.0, "random_state": 42},
        "ranking_rule": "First complete-universe eligible session each month, skip overlapping 20-session targets; select top 10 of 50 on identical dates.",
        "risk_metrics": ["mae", "rmse", "r2", "class_precision_recall_f1"],
        "return_metrics": ["rank_ic", "selected_minus_universe",
                           "selected_minus_momentum", "per_date_results"],
        "source_limitations": ["Saved test scores were previously exposed; this is not independent confirmation.",
                               "Raw source checksum and historical identity issues remain unresolved.",
                               "SEC assets and cash research features are excluded.",
                               "Selected returns begin at the observed close; no Shariah screen or trading costs."],
    }


def cohort_masks(frame, factors, test_start, columns):
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/date keys")
    if not set(frame.dataset_split.dropna().unique()).issubset(
            {"train", "validation", "test", "purged", "unlabeled"}):
        raise ValueError("Unexpected saved split")
    ready = factors[columns].notna().all(axis=1)
    labeled = frame[["risk_volatility_next_20d", "return_next_20d", "target_window_end"]].notna().all(axis=1)
    test_dates = frame.loc[frame.dataset_split.eq("test"), "session_date"]
    if test_dates.empty or test_dates.min() != test_start:
        raise ValueError("Saved test boundary differs from frozen protocol")
    train = (frame.session_date.lt(test_start) & frame.target_window_end.lt(test_start)
             & ready & labeled)
    evaluation = frame.dataset_split.eq("test") & frame.session_date.ge(test_start) & ready & labeled
    if not train.any() or not evaluation.any():
        raise ValueError("No usable training or evaluation rows")
    if frame.loc[train, "target_window_end"].max() >= frame.loc[evaluation, "session_date"].min():
        raise AssertionError("Training label overlaps evaluation")
    if frame.loc[evaluation, "target_window_end"].max() > frame.session_date.max():
        raise AssertionError("Evaluation label extends beyond saved price dates")
    return train, evaluation


def class_rows(actual, predicted, boundaries, name):
    report = classification_report(classes(actual, boundaries), classes(predicted, boundaries),
                                   labels=CLASSES, output_dict=True, zero_division=0)
    return [{"model": name, "class": label, "precision": report[label]["precision"],
             "recall": report[label]["recall"], "f1": report[label]["f1-score"],
             "support": report[label]["support"]} for label in [*CLASSES, "macro avg"]]


def score_risk(actual, predicted, name):
    return {"model": name, "rows": len(actual),
            "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted))}


def evaluate(protocol_path):
    protocol_path = Path(protocol_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    data_path = Path(protocol["dataset"])
    meta_path = data_path.with_name("targets_metadata.json")
    for path, expected in ((data_path, protocol["dataset_sha256"]),
                           (meta_path, protocol["target_metadata_sha256"]),
                           (Path(protocol["selection_source"]) / "manifest.json", protocol["development_manifest_sha256"]),
                           (Path(protocol["selection_source"]) / "risk_summary.csv", protocol["development_risk_summary_sha256"]),
                           (Path(protocol["selection_source"]) / "return_vs_momentum_summary.csv", protocol["development_return_comparison_sha256"]),
                           (THIS_CODE, protocol["code_sha256"]["final_evaluation.py"]),
                           (MODEL_CODE, protocol["code_sha256"]["walk_forward.py"]),
                           (FEATURE_CODE, protocol["code_sha256"]["market.py"])):
        if digest(path) != expected:
            raise ValueError(f"Frozen input changed: {path}")
    columns = protocol["risk_model"]["feature_columns"]
    if columns != feature_sets()["03_market_relative"]:
        raise ValueError("Frozen feature order changed")
    frame = pd.read_csv(data_path, low_memory=False)
    factors = build_market_features(frame)
    train, test = cohort_masks(frame, factors, protocol["test_start"], columns)
    risk_train = frame.loc[train, "risk_volatility_next_20d"]
    return_train = frame.loc[train, "return_next_20d"]
    risk_cut, return_cut = thresholds(risk_train), thresholds(return_train)

    risk_model = estimator("ridge")
    risk_model.fit(factors.loc[train, columns], risk_train)
    risk_actual = frame.loc[test, "risk_volatility_next_20d"].to_numpy()
    risk_prediction = risk_model.predict(factors.loc[test, columns])
    risk_baseline = factors.loc[test, "volatility_20d"].to_numpy()
    risk_scores = pd.DataFrame([score_risk(risk_actual, risk_baseline, "trailing_volatility_20d"),
                                score_risk(risk_actual, risk_prediction, "ridge_market_relative")])
    reports = class_rows(risk_actual, risk_baseline, risk_cut, "trailing_volatility_20d")
    reports += class_rows(risk_actual, risk_prediction, risk_cut, "ridge_market_relative")

    return_model = estimator("hist_gbm")
    return_model.fit(factors.loc[train, columns], return_train)
    candidates = frame.loc[test, ["ticker", "session_date", "target_window_end", "return_next_20d"]].copy()
    candidates["momentum_20d"] = factors.loc[test, "momentum_20d"].to_numpy()
    candidates["learned_score"] = return_model.predict(factors.loc[test, columns])
    reports += class_rows(candidates.return_next_20d.to_numpy(),
                          candidates.learned_score.to_numpy(), return_cut,
                          "hist_gbm_return_challenger")
    dates = rebalance_dates(candidates)
    if not dates:
        raise ValueError("No separated full-universe rebalance dates")
    details = []
    for date, end in dates:
        block = candidates[candidates.session_date.eq(date)]
        for column, name in (("momentum_20d", "momentum_20d"),
                             ("learned_score", "hist_gbm_return_challenger")):
            details.append({"rebalance_date": date, "target_window_end": end,
                            "ranking": name, "candidates": len(block), "selected": TOP_N,
                            **rank_metrics(block, column)})
    details = pd.DataFrame(details)
    summary = details.groupby("ranking").agg(
        dates=("rebalance_date", "nunique"), mean_rank_ic=("rank_ic", "mean"),
        mean_selected_return=("selected_forward_return", "mean"),
        mean_universe_return=("universe_forward_return", "mean"),
        mean_spread=("selected_minus_universe", "mean"),
        positive_spread_dates=("selected_minus_universe", lambda x: int((x > 0).sum()))).reset_index()
    benchmark = details[details.ranking.eq("momentum_20d")][
        ["rebalance_date", "selected_minus_universe"]].rename(
            columns={"selected_minus_universe": "momentum_spread"})
    paired = details[details.ranking.ne("momentum_20d")].merge(
        benchmark, on="rebalance_date", validate="one_to_one")
    paired["spread_minus_momentum"] = paired.selected_minus_universe - paired.momentum_spread
    if len(paired) != len(dates):
        raise AssertionError("Challenger and momentum dates differ")
    result = {"protocol_sha256": digest(protocol_path),
              "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": protocol["status"], "dataset_sha256": protocol["dataset_sha256"],
              "code_sha256": protocol["code_sha256"],
              "train_rows": int(train.sum()), "test_rows": int(test.sum()),
              "train_first_date": frame.loc[train, "session_date"].min(),
              "train_last_feature_date": frame.loc[train, "session_date"].max(),
              "train_last_label_end": frame.loc[train, "target_window_end"].max(),
              "test_first_date": frame.loc[test, "session_date"].min(),
              "test_last_feature_date": frame.loc[test, "session_date"].max(),
              "test_last_label_end": frame.loc[test, "target_window_end"].max(),
              "risk_thresholds_training_only": risk_cut,
              "return_thresholds_training_only": return_cut,
              "rebalance_dates": [x[0] for x in dates],
              "paired_challenger_minus_momentum_mean_spread": float(paired.spread_minus_momentum.mean()),
              "paired_challenger_wins": int(paired.spread_minus_momentum.gt(0).sum()),
              "limitations": protocol["source_limitations"]}
    return result, risk_scores, pd.DataFrame(reports), summary, details, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "evaluate"])
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.action == "freeze":
        if args.protocol:
            parser.error("--protocol is only for evaluate")
        out = args.output_dir or ROOT / "reports/generated" / f"final_protocol_{stamp}"
        out.mkdir(parents=True, exist_ok=False)
        path = out / "protocol.json"
        path.write_text(json.dumps(frozen_protocol(), indent=2), encoding="utf-8")
        print(f"Frozen protocol: {path}")
        return
    if args.protocol is None:
        parser.error("evaluate requires --protocol")
    result, risk_scores, classes_out, return_summary, details, paired = evaluate(args.protocol)
    out = args.output_dir or ROOT / "reports/generated" / f"final_evaluation_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for name, frame in (("risk_scores", risk_scores), ("class_reports", classes_out),
                        ("return_summary", return_summary), ("rebalance_details", details),
                        ("return_vs_momentum", paired)):
        frame.to_csv(out / f"{name}.csv", index=False)
    print(f"Saved reused-test check: {out}")
    print(risk_scores.to_string(index=False))
    print(return_summary.to_string(index=False))
    print(f"Challenger minus momentum spread: {result['paired_challenger_minus_momentum_mean_spread']:.6f}")


if __name__ == "__main__":
    main()
