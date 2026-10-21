"""Compare existing raw inputs with trailing market factors on validation only.

Run from the repository root:
    python -m src.modeling.compare_features

This experiment reuses the existing 20-session labels, purged chronological
splits and training-only thresholds. It deliberately does not inspect test
labels or save a deployable model.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features.market import FEATURE_COLUMNS, build_market_features


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data/modeling/20261009T115557984450Z/model_dataset.csv"
TARGETS = {
    "risk_class": ("risk_class_next_20d", "classification"),
    "risk_regression": ("risk_volatility_next_20d", "regression"),
    "return_class": ("return_class_next_20d", "classification"),
    "return_regression": ("return_next_20d", "regression"),
    "excess_return_class": ("excess_return_class_next_20d", "classification"),
    "excess_return_regression": ("excess_return_next_20d", "regression"),
}


def models(kind):
    if kind == "classification":
        return {
            "dummy": DummyClassifier(strategy="most_frequent"),
            "logistic": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                      LogisticRegression(max_iter=1000, random_state=42)),
            "hist_gbm": make_pipeline(SimpleImputer(strategy="median"),
                                      HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15,
                                                                     l2_regularization=1.0, random_state=42)),
        }
    return {
        "dummy": DummyRegressor(strategy="mean"),
        "ridge": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=100.0)),
        "hist_gbm": make_pipeline(SimpleImputer(strategy="median"),
                                  HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=15,
                                                                l2_regularization=1.0, random_state=42)),
    }


def evaluate(data_path: Path) -> tuple[dict, pd.DataFrame]:
    metadata_path = data_path.with_name("targets_metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source = pd.read_csv(data_path, low_memory=False)
    if source.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/session_date keys")
    if not set(source.dataset_split.unique()).issubset({"train", "validation", "test", "purged", "unlabeled"}):
        raise ValueError("Unexpected split name")
    train = source.dataset_split.eq("train")
    val = source.dataset_split.eq("validation")
    if not train.any() or not val.any():
        raise ValueError("Training and validation rows are required")
    if source.loc[train, "target_window_end"].max() >= source.loc[val, "session_date"].min():
        raise ValueError("Training labels overlap validation")
    if not set(metadata["feature_columns"]).isdisjoint(metadata["target_columns"]):
        raise ValueError("Target found in original feature allowlist")

    factors = build_market_features(source)
    ready = factors.notna().all(axis=1)
    # Same rows for both feature sets, so score differences measure inputs.
    cohort = (train | val) & ready
    if not cohort.any():
        raise ValueError("No eligible factor rows")
    feature_sets = {"original_raw": source[metadata["feature_columns"]], "trailing_factors": factors}
    rows = []
    for feature_set, features in feature_sets.items():
        columns = list(features.columns)
        if set(columns) & set(metadata["target_columns"]):
            raise ValueError("A target entered the feature matrix")
        for task, (target, kind) in TARGETS.items():
            eligible = cohort & source[target].notna()
            train_rows = eligible & train
            val_rows = eligible & val
            x_train = features.loc[train_rows, columns]
            x_val = features.loc[val_rows, columns]
            y_train = source.loc[train_rows, target]
            y_val = source.loc[val_rows, target]
            if len(x_train) < 100 or len(x_val) < 100:
                raise ValueError(f"Insufficient eligible rows for {task}")
            for name, estimator in models(kind).items():
                estimator.fit(x_train, y_train)
                prediction = estimator.predict(x_val)
                row = dict(feature_set=feature_set, task=task, model=name,
                           train_rows=len(x_train), validation_rows=len(x_val))
                if kind == "classification":
                    row.update(accuracy=float(accuracy_score(y_val, prediction)),
                               macro_f1=float(f1_score(y_val, prediction, average="macro")))
                else:
                    row.update(mae=float(mean_absolute_error(y_val, prediction)),
                               rmse=float(np.sqrt(mean_squared_error(y_val, prediction))),
                               r2=float(r2_score(y_val, prediction)))
                    # Correlate stocks within each session before averaging
                    # sessions; these overlapping dates are not independent.
                    ranks = pd.DataFrame({"date": source.loc[val_rows, "session_date"].to_numpy(),
                                          "actual": y_val.to_numpy(), "predicted": prediction})
                    daily_ic = ranks.groupby("date").apply(
                        lambda g: g["actual"].corr(g["predicted"], method="spearman")
                        if g["predicted"].nunique() > 1 and g["actual"].nunique() > 1 else np.nan,
                        include_groups=False,
                    ).dropna()
                    row["mean_daily_rank_ic"] = float(daily_ic.mean()) if len(daily_ic) else None
                rows.append(row)
                print(f"{feature_set:16s} {task:18s} {name:9s} "
                      f"macro_f1={row.get('macro_f1', float('nan')):.4f} "
                      f"r2={row.get('r2', float('nan')):.4f}", flush=True)

    report = {
        "dataset": str(data_path.resolve()),
        "dataset_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "target_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "source_rows": len(source),
        "feature_ready_rows": int(ready.sum()),
        "train_rows_compared": int((cohort & train).sum()),
        "validation_rows_compared": int((cohort & val).sum()),
        "train_last_date": source.loc[train, "session_date"].max(),
        "validation_first_date": source.loc[val, "session_date"].min(),
        "validation_last_date": source.loc[val, "session_date"].max(),
        "feature_sets": {key: list(value.columns) for key, value in feature_sets.items()},
        "notes": [
            "Validation only; test labels were not scored or used for model selection.",
            "Both feature sets use the same factor-ready rows.",
            "Existing labels, split dates and training-only class thresholds were retained.",
            "Current corporate-action, bar-availability and issuer-identity flags remain unresolved.",
            "Daily rank IC values share overlapping 20-session outcomes; uncertainty is not estimated here.",
        ],
    }
    return report, pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    report, scores = evaluate(args.data)
    out = args.output_dir or ROOT / "reports/generated" / datetime.now(timezone.utc).strftime("feature_comparison_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    scores.to_csv(out / "validation_scores.csv", index=False)
    (out / "run_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved validation comparison: {out}")


if __name__ == "__main__":
    main()
