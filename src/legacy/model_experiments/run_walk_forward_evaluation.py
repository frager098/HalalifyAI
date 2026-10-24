"""Development-only, shared-date walk-forward risk and return comparisons.

Run: python -m src.legacy.model_experiments.run_walk_forward_evaluation
The saved test period is excluded. Scores are research diagnostics while data
provenance and historical security identity remain unresolved.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import classification_report, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.feature_engineering.market_features import build_market_features
from src.legacy.model_experiments.compare_feature_sets import DEFAULT_DATA, ROOT


LABEL_HORIZON = 20
FOLDS = 4
EVALUATION_SESSIONS = 252
TOP_N = 10
CLASSES = ["low", "medium", "high"]
FEATURE_GROUPS = {
    "01_momentum_volatility": ["momentum_20d", "momentum_60d", "volatility_20d", "volatility_60d"],
    "02_trend_downside": ["return_1d", "price_to_sma20", "price_to_sma50",
                          "downside_dev_20d", "drawdown_from_peak_60d"],
    "03_market_relative": ["spy_momentum_20d", "excess_momentum_20d", "market_beta_60d"],
    "04_volume": ["volume_ratio_20d"],
}


def feature_sets():
    selected = []
    result = {}
    for name, columns in FEATURE_GROUPS.items():
        selected += columns
        result[name] = selected.copy()
    return result


def thresholds(training_values):
    values = np.asarray(training_values, dtype=float)
    if len(values) < 100 or not np.isfinite(values).all():
        raise ValueError("Too few finite training targets for class thresholds")
    low, high = np.quantile(values, [1 / 3, 2 / 3])
    if low >= high:
        raise ValueError("Training tertile boundaries are not distinct")
    return float(low), float(high)


def classes(values, boundaries):
    values = np.asarray(values, dtype=float)
    return np.where(values <= boundaries[0], "low",
                    np.where(values <= boundaries[1], "medium", "high"))


def development_folds(frame, test_start, n_splits=FOLDS, test_size=EVALUATION_SESSIONS):
    """Split shared dates; independently purge using actual target end dates."""
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/session keys")
    dates = np.array(sorted(frame.loc[frame.session_date.lt(test_start), "session_date"].unique()))
    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=test_size, gap=LABEL_HORIZON)
    target_end = frame.target_window_end
    for number, (train_dates_idx, eval_dates_idx) in enumerate(splitter.split(dates), 1):
        train_dates, eval_dates = dates[train_dates_idx], dates[eval_dates_idx]
        eval_start, eval_end = eval_dates[0], eval_dates[-1]
        train = frame.session_date.isin(train_dates) & target_end.notna() & target_end.lt(eval_start)
        evaluation = (frame.session_date.isin(eval_dates) & target_end.notna()
                      & target_end.le(eval_end) & target_end.lt(test_start))
        if not train.any() or not evaluation.any():
            raise ValueError(f"Fold {number} has no usable rows")
        train_last_end = target_end.loc[train].max()
        eval_last_end = target_end.loc[evaluation].max()
        if train_last_end >= eval_start or eval_last_end > eval_end:
            raise AssertionError("Forward label overlaps next evaluation period")
        gap_dates = dates[train_dates_idx[-1] + 1:eval_dates_idx[0]]
        yield number, train, evaluation, {
            "fold": number, "train_first_date": train_dates[0],
            "train_last_feature_date": train_dates[-1],
            "train_last_label_end": train_last_end,
            "gap_first_date": gap_dates[0], "gap_last_date": gap_dates[-1],
            "gap_sessions": len(gap_dates),
            "evaluation_first_date": eval_start,
            "evaluation_last_feature_date": eval_end,
            "evaluation_last_label_end": eval_last_end,
            "train_rows": int(train.sum()), "evaluation_rows": int(evaluation.sum()),
            "train_label_before_evaluation": True,
            "evaluation_label_within_period": True,
            "held_out_test_untouched": True,
        }


def estimator(name):
    if name == "ridge":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=100.0))
    if name == "hist_gbm":
        return make_pipeline(SimpleImputer(strategy="median"),
                             HistGradientBoostingRegressor(max_iter=50, max_leaf_nodes=15,
                                                           l2_regularization=1.0,
                                                           early_stopping=False, random_state=42))
    raise ValueError(name)


def rank_metrics(block, score):
    if block[score].nunique() <= 1 or block.return_next_20d.nunique() <= 1:
        ic = np.nan
    else:
        ic = float(block[score].corr(block.return_next_20d, method="spearman"))
    chosen = block.sort_values([score, "ticker"], ascending=[False, True]).head(TOP_N)
    return {"rank_ic": ic,
            "selected_forward_return": float(chosen.return_next_20d.mean()),
            "universe_forward_return": float(block.return_next_20d.mean()),
            "selected_minus_universe": float(chosen.return_next_20d.mean() - block.return_next_20d.mean()),
            "selected_tickers": ",".join(chosen.ticker)}


def rebalance_dates(frame):
    """One complete-universe first session per month, separated by label ends."""
    monthly = frame.groupby(frame.session_date.str.slice(0, 7)).session_date.min().tolist()
    selected, prior_end = [], ""
    for date in monthly:
        block = frame[frame.session_date.eq(date)]
        if len(block) != 50 or block.ticker.nunique() != 50:
            continue
        ends = block.target_window_end.unique()
        if len(ends) != 1:
            raise ValueError(f"Inconsistent target end on {date}")
        if date > prior_end:
            selected.append((date, ends[0]))
            prior_end = ends[0]
    return selected


def run(data_path=DEFAULT_DATA, n_splits=FOLDS, test_size=EVALUATION_SESSIONS):
    data_path = Path(data_path)
    meta_path = data_path.with_name("targets_metadata.json")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if hashlib.sha256(data_path.read_bytes()).hexdigest() != metadata["output_sha256"]:
        raise ValueError("Model dataset checksum differs from its metadata")
    frame = pd.read_csv(data_path, low_memory=False)
    test_start = metadata["test_start"]
    # Trailing features may be computed on the development slice alone.
    frame = frame[frame.session_date.lt(test_start)].copy().reset_index(drop=True)
    features = build_market_features(frame)
    groups = feature_sets()
    if set(sum(groups.values(), [])) & set(metadata["target_columns"]):
        raise ValueError("Future target in feature set")
    common_ready = (features[list(groups.values())[-1]].notna().all(axis=1)
                    & frame[["risk_volatility_next_20d", "return_next_20d"]].notna().all(axis=1))
    fold_rows, score_rows, class_rows, rank_rows = [], [], [], []
    for fold, train_base, eval_base, info in development_folds(frame, test_start, n_splits, test_size):
        train, evaluation = train_base & common_ready, eval_base & common_ready
        if train.sum() < 1000 or evaluation.sum() < 1000:
            raise ValueError(f"Fold {fold}: too few common-ready rows")
        info.update(train_common_rows=int(train.sum()), evaluation_common_rows=int(evaluation.sum()))
        risk_cut = thresholds(frame.loc[train, "risk_volatility_next_20d"])
        return_cut = thresholds(frame.loc[train, "return_next_20d"])
        info.update(risk_low_threshold=risk_cut[0], risk_high_threshold=risk_cut[1],
                    return_low_threshold=return_cut[0], return_high_threshold=return_cut[1])
        fold_rows.append(info)
        candidates = frame.loc[evaluation, ["ticker", "session_date", "target_window_end",
                                                  "return_next_20d"]].copy()
        candidates["momentum_20d"] = features.loc[evaluation, "momentum_20d"].to_numpy()
        dates = rebalance_dates(candidates)
        if len(dates) < 3:
            raise ValueError(f"Fold {fold}: too few separated complete-universe rebalances")
        info["rebalance_dates"] = len(dates)
        for group, columns in groups.items():
            for model_name in ("ridge", "hist_gbm"):
                predictions = {}
                for task, target, cut in (("risk", "risk_volatility_next_20d", risk_cut),
                                          ("return", "return_next_20d", return_cut)):
                    fitted = estimator(model_name)
                    fitted.fit(features.loc[train, columns], frame.loc[train, target])
                    predicted = fitted.predict(features.loc[evaluation, columns])
                    predictions[task] = predicted
                    actual = frame.loc[evaluation, target].to_numpy()
                    entry = {"fold": fold, "task": task, "feature_group": group, "model": model_name,
                             "train_rows": int(train.sum()), "evaluation_rows": int(evaluation.sum()),
                             "mae": float(mean_absolute_error(actual, predicted)),
                             "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
                             "r2": float(r2_score(actual, predicted))}
                    score_rows.append(entry)
                    report = classification_report(classes(actual, cut), classes(predicted, cut),
                                                   labels=CLASSES, output_dict=True, zero_division=0)
                    for label in [*CLASSES, "macro avg"]:
                        class_rows.append({"fold": fold, "task": task, "feature_group": group,
                                           "model": model_name, "class": label,
                                           "precision": report[label]["precision"],
                                           "recall": report[label]["recall"],
                                           "f1": report[label]["f1-score"],
                                           "support": report[label]["support"]})
                candidates["prediction"] = predictions["return"]
                for date, end in dates:
                    block = candidates[candidates.session_date.eq(date)]
                    for ranking in ("momentum_20d", "prediction"):
                        rank_rows.append({"fold": fold, "feature_group": group,
                                          "model": "momentum_20d" if ranking == "momentum_20d" else model_name,
                                          "rebalance_date": date, "target_window_end": end,
                                          "candidates": len(block), "selected": TOP_N,
                                          **rank_metrics(block, ranking)})
        # The trailing 20-day volatility itself is the zero-fit risk benchmark.
        actual_risk = frame.loc[evaluation, "risk_volatility_next_20d"].to_numpy()
        baseline = features.loc[evaluation, "volatility_20d"].to_numpy()
        score_rows.append({"fold": fold, "task": "risk", "feature_group": "benchmark",
                           "model": "trailing_volatility_20d", "train_rows": int(train.sum()),
                           "evaluation_rows": int(evaluation.sum()),
                           "mae": float(mean_absolute_error(actual_risk, baseline)),
                           "rmse": float(np.sqrt(mean_squared_error(actual_risk, baseline))),
                           "r2": float(r2_score(actual_risk, baseline))})
        report = classification_report(classes(actual_risk, risk_cut), classes(baseline, risk_cut),
                                       labels=CLASSES, output_dict=True, zero_division=0)
        for label in [*CLASSES, "macro avg"]:
            class_rows.append({"fold": fold, "task": "risk", "feature_group": "benchmark",
                               "model": "trailing_volatility_20d", "class": label,
                               "precision": report[label]["precision"], "recall": report[label]["recall"],
                               "f1": report[label]["f1-score"], "support": report[label]["support"]})
        print(f"Fold {fold}: {info['evaluation_first_date']} to {info['evaluation_last_feature_date']}, "
              f"{len(dates)} separated rebalances", flush=True)
    folds = pd.DataFrame(fold_rows)
    scores = pd.DataFrame(score_rows)
    classes_out = pd.DataFrame(class_rows)
    ranks = pd.DataFrame(rank_rows).drop_duplicates(
        ["fold", "feature_group", "model", "rebalance_date"])
    risk_summary = scores[scores.task.eq("risk")].groupby(["feature_group", "model"]).agg(
        folds=("fold", "nunique"), mean_mae=("mae", "mean"), mean_r2=("r2", "mean"),
        sd_r2=("r2", "std"), min_r2=("r2", "min"), max_r2=("r2", "max")).reset_index()
    rank_fold = ranks.groupby(["fold", "feature_group", "model"]).agg(
        dates=("rebalance_date", "nunique"), mean_rank_ic=("rank_ic", "mean"),
        mean_spread=("selected_minus_universe", "mean"),
        positive_spread_dates=("selected_minus_universe", lambda x: int((x > 0).sum()))).reset_index()
    rank_summary = rank_fold.groupby(["feature_group", "model"]).agg(
        folds=("fold", "nunique"), total_dates=("dates", "sum"),
        mean_rank_ic=("mean_rank_ic", "mean"), sd_fold_rank_ic=("mean_rank_ic", "std"),
        mean_spread=("mean_spread", "mean"), sd_fold_spread=("mean_spread", "std"),
        min_fold_spread=("mean_spread", "min"), max_fold_spread=("mean_spread", "max"),
        positive_spread_dates=("positive_spread_dates", "sum")).reset_index()
    baseline = ranks[ranks.model.eq("momentum_20d")][
        ["fold", "feature_group", "rebalance_date", "target_window_end", "candidates",
         "universe_forward_return", "rank_ic", "selected_minus_universe"]].rename(
             columns={"rank_ic": "momentum_rank_ic",
                      "selected_minus_universe": "momentum_spread"})
    paired = ranks[ranks.model.ne("momentum_20d")].merge(
        baseline, on=["fold", "feature_group", "rebalance_date", "target_window_end",
                      "candidates", "universe_forward_return"], how="inner", validate="many_to_one")
    if len(paired) != len(ranks[ranks.model.ne("momentum_20d")]):
        raise AssertionError("Learned rankings and momentum do not have identical candidate dates")
    paired["spread_minus_momentum"] = paired.selected_minus_universe - paired.momentum_spread
    paired["rank_ic_minus_momentum"] = paired.rank_ic - paired.momentum_rank_ic
    paired_fold = paired.groupby(["fold", "feature_group", "model"]).agg(
        dates=("rebalance_date", "nunique"), mean_spread_minus_momentum=("spread_minus_momentum", "mean"),
        mean_rank_ic_minus_momentum=("rank_ic_minus_momentum", "mean"),
        dates_beating_momentum=("spread_minus_momentum", lambda x: int((x > 0).sum()))).reset_index()
    paired_summary = paired_fold.groupby(["feature_group", "model"]).agg(
        folds=("fold", "nunique"), dates=("dates", "sum"),
        mean_spread_minus_momentum=("mean_spread_minus_momentum", "mean"),
        sd_fold_spread_minus_momentum=("mean_spread_minus_momentum", "std"),
        folds_beating_momentum=("mean_spread_minus_momentum", lambda x: int((x > 0).sum())),
        dates_beating_momentum=("dates_beating_momentum", "sum")).reset_index()
    manifest = {"dataset_sha256": metadata["output_sha256"], "metadata_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
                "test_start_exclusive": test_start, "development_source_rows": len(frame),
                "folds": n_splits, "nominal_evaluation_sessions": test_size, "gap_sessions": LABEL_HORIZON,
                "feature_sets": groups, "models": {"ridge_alpha": 100.0, "hist_gbm_max_iter": 50,
                                                   "hist_gbm_max_leaf_nodes": 15, "random_state": 42},
                "selection": "First complete-universe session each month; skip overlap with prior 20-session target window; top 10 of 50.",
                "limitations": ["Development research only; prior notebooks have already exposed saved test scores.",
                                "Neither prices nor historical ticker identities are fully verified.",
                                "Forward returns begin at the known close, so selected returns are diagnostics rather than executable net returns.",
                                "Fold standard deviations describe period variation, not independent confidence intervals."]}
    return (manifest, folds, scores, classes_out, ranks, risk_summary, rank_fold,
            rank_summary, paired, paired_fold, paired_summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    results = run(args.data)
    out = args.output_dir or ROOT / "reports/generated/legacy/modeling" / datetime.now(timezone.utc).strftime("walk_forward_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    names = ["manifest", "folds", "per_fold_scores", "class_reports", "rebalance_details",
             "risk_summary", "return_rank_per_fold", "return_rank_summary",
             "return_vs_momentum_per_date", "return_vs_momentum_per_fold",
             "return_vs_momentum_summary"]
    for name, value in zip(names, results):
        path = out / (name + (".json" if name == "manifest" else ".csv"))
        if name == "manifest":
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        else:
            value.to_csv(path, index=False)
    print(f"Saved: {out}")
    print(results[5].to_string(index=False))
    print(results[7].to_string(index=False))
    print(results[10].to_string(index=False))


if __name__ == "__main__":
    main()
