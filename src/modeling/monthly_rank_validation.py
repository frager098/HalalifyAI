"""Evaluate 20-session return ranking on separated validation rebalance dates.

Run: python -m src.modeling.monthly_rank_validation
Uses only the existing training and validation splits. This is a research
selection diagnostic, not a Shariah-screened portfolio backtest.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.market import build_market_features
from src.modeling.compare_features import DEFAULT_DATA, ROOT, models


TOP_N = 10  # 20 percent of the fixed 50-stock research universe.


def choose_rebalance_dates(frame):
    """First eligible session in each complete validation month, no label overlap."""
    dates = sorted(frame.session_date.unique())
    if not dates:
        raise ValueError("No validation dates")
    first_partial_month = dates[0][:7]
    candidates = [date for date in dates if date[:7] != first_partial_month]
    monthly = {}
    for date in candidates:
        monthly.setdefault(date[:7], date)
    selected = []
    previous_end = ""
    for date in monthly.values():
        block = frame[frame.session_date.eq(date)]
        if block.ticker.nunique() != 50:
            continue
        ends = block.target_window_end.dropna().unique()
        if len(ends) != 1:
            raise ValueError(f"Inconsistent target window end on {date}")
        if date > previous_end:
            selected.append((date, ends[0]))
            previous_end = ends[0]
    if len(selected) < 3:
        raise ValueError("Too few separated validation dates")
    return selected


def evaluate(data_path=DEFAULT_DATA):
    data_path = Path(data_path)
    metadata = json.loads(data_path.with_name("targets_metadata.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(data_path, low_memory=False)
    factors = build_market_features(frame)
    ready = factors.notna().all(axis=1)
    train = frame.dataset_split.eq("train") & ready & frame.return_next_20d.notna()
    validation = frame.dataset_split.eq("validation") & ready & frame.return_next_20d.notna()
    if frame.loc[train, "target_window_end"].max() >= frame.loc[validation, "session_date"].min():
        raise ValueError("Training labels overlap validation")
    if frame.loc[validation, "target_window_end"].max() >= frame.loc[frame.dataset_split.eq("test"), "session_date"].min():
        raise ValueError("Validation labels overlap test")
    raw = frame[metadata["feature_columns"]]
    fitted = {}
    for name, inputs, model_name in [
        ("raw_ridge", raw, "ridge"),
        ("factor_ridge", factors, "ridge"),
        ("factor_hist_gbm", factors, "hist_gbm"),
    ]:
        estimator = models("regression")[model_name]
        estimator.fit(inputs.loc[train], frame.loc[train, "return_next_20d"])
        fitted[name] = estimator.predict(inputs.loc[validation])

    candidates = frame.loc[validation, ["ticker", "session_date", "target_window_end",
                                        "return_next_20d"]].copy()
    candidates["momentum_20d"] = factors.loc[validation, "momentum_20d"].to_numpy()
    for name, prediction in fitted.items():
        candidates[name] = prediction
    dates = choose_rebalance_dates(candidates)
    details = []
    for date, end in dates:
        block = candidates[candidates.session_date.eq(date)].copy()
        universe = float(block.return_next_20d.mean())
        for name in ["momentum_20d", *fitted]:
            selected = block.sort_values([name, "ticker"], ascending=[False, True]).head(TOP_N)
            selected_return = float(selected.return_next_20d.mean())
            ic = float(block[name].corr(block.return_next_20d, method="spearman"))
            details.append({
                "rebalance_date": date,
                "window_end": end,
                "ranking": name,
                "candidates": len(block),
                "selected": len(selected),
                "rank_ic": ic,
                "selected_forward_return": selected_return,
                "universe_forward_return": universe,
                "selected_minus_universe": selected_return - universe,
                "selected_tickers": ",".join(selected.ticker),
            })
    detail = pd.DataFrame(details)
    summary = detail.groupby("ranking").agg(
        rebalance_dates=("rebalance_date", "nunique"),
        mean_rank_ic=("rank_ic", "mean"),
        mean_selected_forward_return=("selected_forward_return", "mean"),
        mean_universe_forward_return=("universe_forward_return", "mean"),
        mean_selected_minus_universe=("selected_minus_universe", "mean"),
        positive_spread_dates=("selected_minus_universe", lambda x: int((x > 0).sum())),
    ).reset_index()
    manifest = {
        "dataset_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "selection": "First eligible session of each complete validation month; skip dates whose 20-session target window overlaps the previous selected window.",
        "first_partial_validation_month_excluded": frame.loc[validation, "session_date"].min()[:7],
        "rebalance_dates": [date for date, _ in dates],
        "top_n": TOP_N,
        "train_rows": int(train.sum()),
        "validation_rows": int(validation.sum()),
        "notes": [
            "Only existing training and validation labels were used.",
            "All four rankings use identical candidates and forward-return labels.",
            "Return figures are average 20-session returns per selected date, not cumulative or annualized backtest returns.",
            "No Shariah screen, costs, slippage or historical universe changes were applied.",
            "The number of separated validation dates is small; differences may be noise.",
        ],
    }
    return manifest, summary, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    manifest, summary, detail = evaluate(args.data)
    out = args.output_dir or ROOT / "reports/generated" / datetime.now(timezone.utc).strftime("monthly_rank_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    summary.to_csv(out / "summary.csv", index=False)
    detail.to_csv(out / "rebalance_details.csv", index=False)
    (out / "run_metadata.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Saved monthly ranking comparison: {out}")


if __name__ == "__main__":
    main()
