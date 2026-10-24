"""Audit and freeze chronological Phase 4 folds without fitting models.

Run: python -m src.model_training.chronological_evaluation_protocol --output reports/generated/current/chronological_evaluation_protocol.json
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.build_feature_dataset import UNIVERSE, sha256

DEFAULT_DATA = Path("data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv")
OUTER_FOLDS = 4
OUTER_SESSIONS = 252
INNER_SESSIONS = 126


def _hash_keys(frame):
    keys = frame[["ticker", "session_date"]].sort_values(["ticker", "session_date"])
    return hashlib.sha256(keys.to_csv(index=False, lineterminator="\n").encode()).hexdigest()


def load_and_audit(path):
    path = Path(path)
    metadata = json.loads((path.parent / "dataset_metadata.json").read_text(encoding="utf-8"))
    if sha256(path) != metadata["output_sha256"]:
        raise ValueError("Dataset checksum differs from metadata")
    frame = pd.read_csv(path, low_memory=False)
    required = {"ticker", "session_date", "target_window_end", "nominal_split",
                "active_peer_count", "outcome_peer_count", "activity_quorum_met",
                "return_next_20d", "risk_volatility_next_20d", "relative_return_class",
                "risk_class", "return_eligible", "risk_eligible", "return_eligibility_reason",
                "risk_eligibility_reason", *FEATURE_COLUMNS}
    if required - set(frame) or set(FEATURE_COLUMNS) != set(metadata["feature_columns"]):
        raise ValueError("Dataset schema or feature allowlist mismatch")
    if len(frame) != metadata["rows"] or frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Unexpected row count or duplicate keys")
    if not set(frame.ticker).issubset(set(UNIVERSE)) or frame.ticker.eq("SPY").any():
        raise ValueError("Unexpected ticker")
    if frame.session_date.isna().any() or pd.to_datetime(frame.session_date, errors="coerce").isna().any():
        raise ValueError("Invalid session date")
    end = pd.to_datetime(frame.target_window_end, errors="coerce")
    if (end.notna() & end.le(pd.to_datetime(frame.session_date))).any():
        raise ValueError("Target ends before or on prediction date")
    shared_dates = pd.Index(sorted(frame.session_date.unique()))
    expected_ends = pd.Series(shared_dates, index=shared_dates).shift(-20)
    observed_ends = frame.session_date.map(expected_ends)
    if not observed_ends.fillna("").eq(frame.target_window_end.fillna("")).all():
        raise ValueError("Target end does not match shared 20-session horizon")
    if not frame.loc[frame.target_window_end.notna(), "target_window_end"].str.match(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Invalid target end")
    if not frame.relative_return_class.dropna().isin([0, 1, 2]).all() or not frame.risk_class.dropna().isin([0, 1, 2]).all():
        raise ValueError("Unexpected class code")
    if not frame.nominal_split.isin(["train", "validation", "reused_test"]).all():
        raise ValueError("Unexpected split")
    forbidden = {"target_window_end", "relative_return_class", "risk_class", "dataset_split", "nominal_split"}
    if set(FEATURE_COLUMNS) & forbidden or set(metadata["feature_columns"]) & forbidden:
        raise ValueError("Future or split field in feature allowlist")
    for task, label in [("return", "relative_return_class"), ("risk", "risk_class")]:
        eligible = frame[task + "_eligible"]
        reason = frame[task + "_eligibility_reason"]
        if eligible.isna().any() or not eligible.eq(reason.eq("eligible")).all():
            raise ValueError(f"{task}: inconsistent eligibility reason")
        if frame.loc[eligible, FEATURE_COLUMNS + [label, "target_window_end"]].isna().any().any():
            raise ValueError(f"{task}: missing required eligible input")
        if int(eligible.sum()) != metadata["eligible_counts"][task]:
            raise ValueError(f"{task}: eligible count differs from metadata")
    return frame, metadata


def _role(frame, dates, evaluation_start, evaluation_end=None, task="return"):
    mask = frame.session_date.isin(dates) & frame[task + "_eligible"]
    mask &= frame.target_window_end.notna()
    if evaluation_start is not None:
        mask &= frame.target_window_end.lt(evaluation_start)
    if evaluation_end is not None:
        mask &= frame.target_window_end.lt(evaluation_end)
    return frame.loc[mask].copy()


def _risk_boundaries(train):
    low, high = train.risk_volatility_next_20d.quantile([1 / 3, 2 / 3]).to_numpy()
    if not np.isfinite([low, high]).all() or low >= high:
        raise ValueError("Fold risk boundaries are invalid")
    return [float(low), float(high)]


def apply_risk_boundaries(values, boundaries):
    numeric = pd.to_numeric(values, errors="raise")
    if numeric.isna().any():
        raise ValueError("Missing risk outcome")
    return np.select([numeric.le(boundaries[0]), numeric.le(boundaries[1])], [0, 1], default=2)


def assert_fold(train, evaluation, evaluation_start):
    if train.empty or evaluation.empty:
        raise ValueError("Empty train or evaluation role")
    if train.session_date.max() >= evaluation.session_date.min() or evaluation.session_date.min() < evaluation_start:
        raise ValueError("Fold is not chronological")
    if train.target_window_end.isna().any() or train.target_window_end.max() >= evaluation_start:
        raise ValueError("Training outcome overlaps evaluation")
    if set(train.session_date) & set(evaluation.session_date):
        raise ValueError("Same session appears in both roles")
    if train[FEATURE_COLUMNS].isna().any().any() or evaluation[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Missing fold feature")


def guarded_training_features(train, evaluation, columns=FEATURE_COLUMNS):
    """The only feature extraction path for fitted Phase 5 pipelines."""
    if set(columns) - set(FEATURE_COLUMNS):
        raise ValueError("Non-allowlisted feature")
    assert_fold(train, evaluation, evaluation.session_date.min())
    return train[list(columns)].copy(), evaluation[list(columns)].copy()


def fit_training_pipeline(estimator, train, evaluation, target, columns=FEATURE_COLUMNS):
    """Fit a Phase 5 preprocessing/model pipeline only on permitted training rows."""
    if target not in {"relative_return_class", "fold_risk_class", "risk_volatility_next_20d", "return_next_20d"}:
        raise ValueError("Unexpected target; risk classes must be recomputed per fold")
    x_train, x_evaluation = guarded_training_features(train, evaluation, columns)
    if train[target].isna().any():
        raise ValueError("Missing training target")
    estimator.fit(x_train, train[target])
    return estimator, x_evaluation


def guarded_calibration_groups(fit_rows, calibration_rows, outer_evaluation):
    """Reserve separate, earlier dates for fitting and probability calibration."""
    assert_fold(fit_rows, calibration_rows, calibration_rows.session_date.min())
    assert_fold(calibration_rows, outer_evaluation, outer_evaluation.session_date.min())
    return fit_rows.copy(), calibration_rows.copy()


def _summary(frame, train, evaluation, first, task):
    candidate = frame.session_date.lt(first) & frame[task + "_eligible"]
    purged = frame.loc[candidate & frame.target_window_end.ge(first)]
    reasons = frame.loc[frame.session_date.le(evaluation.session_date.max())]
    reasons = reasons.loc[~reasons[task + "_eligible"]]
    return {
        "train_dates": [train.session_date.min(), train.session_date.max()],
        "evaluation_dates": [evaluation.session_date.min(), evaluation.session_date.max()],
        "train_rows": len(train), "evaluation_rows": len(evaluation),
        "train_keys_sha256": _hash_keys(train), "evaluation_keys_sha256": _hash_keys(evaluation),
        "purged_before_evaluation": len(purged), "purged_keys_sha256": _hash_keys(purged),
        "purged_keys": purged[["ticker", "session_date"]].sort_values(["ticker", "session_date"]).values.tolist(),
        "train_last_target_end": train.target_window_end.max(),
        "excluded_by_reason": {str(k): int(v) for k, v in reasons[task + "_eligibility_reason"].value_counts().items()},
        "excluded_by_ticker": {str(k): int(v) for k, v in reasons.ticker.value_counts().items()},
        "excluded_by_date": {str(k): int(v) for k,v in reasons.groupby("session_date").size().items()},
    }


def build_protocol(frame, metadata):
    # The fixed 2024-07 boundary excludes every previously inspected test row.
    test_start = metadata["reused_test_start"]
    dates = np.array(sorted(frame.loc[frame.session_date.lt(test_start), "session_date"].unique()))
    if len(dates) < OUTER_FOLDS * OUTER_SESSIONS + INNER_SESSIONS + 100:
        raise ValueError("Too few development sessions")
    folds = []
    for number in range(OUTER_FOLDS):
        start_index = len(dates) - (OUTER_FOLDS - number) * OUTER_SESSIONS
        outer_dates = dates[start_index:start_index + OUTER_SESSIONS]
        inner_dates = dates[start_index - INNER_SESSIONS:start_index]
        if len(inner_dates) != INNER_SESSIONS or outer_dates[-1] >= test_start:
            raise ValueError("Invalid fold dates")
        train_dates = dates[:start_index]
        inner_train_dates = dates[:start_index - INNER_SESSIONS]
        entry = {"fold": number + 1, "outer_first": outer_dates[0], "outer_last": outer_dates[-1],
                 "inner_first": inner_dates[0], "inner_last": inner_dates[-1], "tasks": {}}
        for task, label in [("return", "relative_return_class"), ("risk", "risk_class")]:
            outer_train = _role(frame, train_dates, outer_dates[0], task=task)
            outer_eval = _role(frame, outer_dates, None, test_start, task)
            inner_train = _role(frame, inner_train_dates, inner_dates[0], task=task)
            inner_eval = _role(frame, inner_dates, outer_dates[0], task=task)
            assert_fold(outer_train, outer_eval, outer_dates[0])
            assert_fold(inner_train, inner_eval, inner_dates[0])
            guarded_training_features(outer_train, outer_eval)
            guarded_training_features(inner_train, inner_eval)
            task_entry = {"outer": _summary(frame, outer_train, outer_eval, outer_dates[0], task),
                          "inner": _summary(frame, inner_train, inner_eval, inner_dates[0], task)}
            if task == "risk":
                for name, train, evaluation in [("outer", outer_train, outer_eval), ("inner", inner_train, inner_eval)]:
                    boundaries = _risk_boundaries(train)
                    task_entry[name]["risk_boundaries"] = boundaries
                    task_entry[name]["train_class_counts"] = np.bincount(apply_risk_boundaries(train.risk_volatility_next_20d, boundaries), minlength=3).tolist()
                    task_entry[name]["evaluation_class_counts"] = np.bincount(apply_risk_boundaries(evaluation.risk_volatility_next_20d, boundaries), minlength=3).tolist()
            else:
                for name, evaluation in [("outer", outer_eval), ("inner", inner_eval)]:
                    groups = evaluation.groupby("session_date").ticker.nunique()
                    if groups.empty or groups.min() < 45 or groups.max() > 50:
                        raise ValueError("Invalid ranking peer group")
                    if not evaluation.groupby("session_date").relative_return_class.apply(lambda s: s.isin([0, 1, 2]).all()).all():
                        raise ValueError("Invalid return classes")
                    task_entry[name]["ranking_dates"] = len(groups)
                    task_entry[name]["ranking_group_counts"] = {str(k): int(v) for k,v in groups.value_counts().items()}
            entry["tasks"][task] = task_entry
        folds.append(entry)
    return {"schema_version": 1, "dataset_sha256": metadata["output_sha256"],
        "code_sha256": {"src/model_training/chronological_evaluation_protocol.py": sha256("src/model_training/chronological_evaluation_protocol.py")},
        "feature_allowlist": FEATURE_COLUMNS, "test_start": test_start,
        "reused_test_status": "inspected earlier; excluded from development folds",
        "fold_rule": {"outer_folds": OUTER_FOLDS, "outer_sessions": OUTER_SESSIONS, "inner_sessions": INNER_SESSIONS,
                      "purge": "training target_window_end < first evaluation session; inner evaluation target_window_end < first outer session"},
        "experiment_protocol": {
            "tasks": {"return": "same-date relative return classes 0/1/2; primary mean within-date Spearman rank correlation",
                      "risk": "fixed training-derived volatility classes 0/1/2; primary macro F1"},
            "secondary_metrics": {"return": ["macro_F1", "per_class_precision_recall", "ordinal_error", "confusion_matrix"],
                                  "risk": ["High_to_Low_count", "High_recall", "ordinal_error", "log_loss", "Brier_score", "confusion_matrix"]},
            "return_rank_score": "P(Higher)-P(Lower); not a percentage return",
            "benchmarks": ["training_class_prior", "momentum_20d_rank", "trailing_volatility_20d_with_fold_risk_cutoffs", "preserved_Ridge_numerical_forecasts", "preserved_SPY_relative_results"],
            "candidates": ["LogisticRegression", "HistGradientBoostingClassifier"],
            "feature_groups": {"momentum_volatility": ["momentum_20d", "momentum_60d", "volatility_20d", "volatility_60d"],
                               "trend_downside": ["return_1d", "price_to_sma20", "price_to_sma50", "downside_dev_20d", "drawdown_from_peak_60d"],
                               "market_relative": ["spy_momentum_20d", "excess_momentum_20d", "market_beta_60d"],
                               "volume": ["volume_ratio_20d"]},
            "search_budget": {"logistic_C": [0.1, 1.0, 10.0],
                              "hist_gbm_max_leaf_nodes": [15, 31, 63],
                              "hist_gbm_fixed": {"max_iter": 100, "learning_rate": 0.1, "early_stopping": False, "random_state": 42},
                              "rule": "Compare baselines and defaults first; use at most these 3 values per model and task on inner validation only."},
            "selection": "Choose on inner validation only, prioritize return rank IC and risk macro F1; report outer results across all folds and severe risk misses. No single-period winner promotion.",
            "preprocessing": "Use allowlisted features only. Fit scaling, any imputation, feature selection, and any calibration on inner training dates. Tuning uses inner validation. Refit selected pipeline on outer training dates. Never fit on outer evaluation dates.",
            "test_rule": "2024-2025 is reused evidence and excluded from development selection. A verified period after 2025-12-31 is a stronger fresh assessment only if code, inputs, thresholds, settings and metrics are frozen before its outcomes are viewed.",
            "ranking_groups": "Evaluate complete same-session eligible peer groups of 45-50 only; fixed 50-name reference universe and average-rank tie policy."},
        "folds": folds}


def run(data_path=DEFAULT_DATA, output=None):
    frame, metadata = load_and_audit(data_path)
    report = build_protocol(frame, metadata)
    if output is not None:
        output = Path(output)
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.data, args.output)
    print(json.dumps({"folds": len(report["folds"]), "output": str(args.output)}))
