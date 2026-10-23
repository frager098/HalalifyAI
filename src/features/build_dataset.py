"""Build the phase 3 features-only dataset; labels and training eligibility follow later."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

from src.features.market import FEATURE_COLUMNS, build_market_features

UNIVERSE = "AAPL MSFT NVDA AMD AVGO ORCL ADBE CRM CSCO INTC GOOGL META NFLX AMZN TSLA HD LOW NKE SBUX MCD COST WMT JNJ LLY ABBV MRK TMO ABT DHR CAT DE HON UPS UNP GE XOM CVX COP SLB JPM BAC GS MS V MA PG KO PEP LIN NEE".split()
VALIDATION_START = "2022-12-28"
TEST_START = "2024-07-01"
DEFAULT_PRICES = "data/cleaned/20261022T060940848455Z/prices_clean.csv"
SELECTED_HASH = "f5734f6b7e3d2e7e41a877834f1cb5210bcb6845e329543459e49eed84959d21"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_prices(frame):
    """Validate bars and derive benchmark returns before any feature calculation."""
    required = {"ticker", "session_date", "open", "high", "low", "close", "volume", "adjusted_close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(required - set(frame.columns))}")
    if frame.empty or frame[["ticker", "session_date"]].isna().any().any():
        raise ValueError("Empty input or missing row keys")
    frame = frame.copy()
    dates = pd.to_datetime(frame.session_date, format="%Y-%m-%d", errors="raise")
    if dates.isna().any():
        raise ValueError("Missing dates")
    frame["session_date"] = dates.dt.strftime("%Y-%m-%d")
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/date keys")
    if set(frame.ticker) - set(UNIVERSE) - {"SPY"}:
        raise ValueError("Unexpected ticker outside reference universe")
    for column in required - {"ticker", "session_date"}:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column]).all():
            raise ValueError(f"Nonfinite {column}")
        if (frame[column] < 0).any() or (column != "volume" and frame[column].eq(0).any()):
            raise ValueError(f"Invalid {column}")
    if (frame.high < frame[["open", "close", "low"]].max(axis=1)).any() or (frame.low > frame[["open", "close"]].min(axis=1)).any():
        raise ValueError("Invalid OHLC bounds")
    calendar = xc.get_calendar("XNYS", start=dates.min() - pd.Timedelta(days=10), end=dates.max() + pd.Timedelta(days=10))
    sessions = calendar.sessions_in_range(dates.min(), dates.max()).tz_localize(None)
    if not dates.isin(sessions).all():
        raise ValueError("Unexpected exchange date")
    spy = frame.loc[frame.ticker.eq("SPY")].set_index("session_date")
    session_strings = sessions.strftime("%Y-%m-%d")
    if spy.empty or not set(session_strings).issubset(spy.index):
        raise ValueError("Missing SPY reference sessions")
    spy = spy.reindex(session_strings)
    spy["spy_return"] = spy.adjusted_close.pct_change(fill_method=None)
    companies = frame.loc[frame.ticker.ne("SPY")].reset_index(drop=True)
    if companies.empty:
        raise ValueError("No company rows")
    companies["spy_return"] = companies.session_date.map(spy.spy_return)
    active = companies.loc[companies.volume.gt(0)].groupby("session_date").ticker.nunique()
    companies["active_peer_count"] = companies.session_date.map(active).fillna(0).astype(int)
    companies["activity_quorum_met"] = companies.active_peer_count.ge(45)
    companies["nominal_split"] = np.select(
        [companies.session_date.lt(VALIDATION_START), companies.session_date.lt(TEST_START)],
        ["train", "validation"], default="reused_test")
    return companies, spy, sessions


def build_dataset(prices=DEFAULT_PRICES, output_dir=None, expected_sha256=SELECTED_HASH):
    prices = Path(prices)
    digest = sha256(prices)
    if digest != expected_sha256:
        raise ValueError("Input checksum mismatch")
    out = Path(output_dir) if output_dir else Path("data/modeling") / ("market_features_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    if out.exists():
        raise FileExistsError(out)
    companies, spy, sessions = prepare_prices(pd.read_csv(prices))
    # Include every benchmark session so a market-wide missing company date
    # cannot disappear from rolling windows. SPY itself is removed afterward.
    benchmark = spy.reset_index().rename(columns={"index": "session_date"})
    combined = pd.concat([companies, benchmark], ignore_index=True)
    features = build_market_features(combined).iloc[:len(companies)].reset_index(drop=True)
    for column in FEATURE_COLUMNS:
        companies[column] = features[column]
    companies["features_complete"] = companies[FEATURE_COLUMNS].notna().all(axis=1)
    metadata = {
        "stage": "features_only", "ready_for_training": False,
        "source": prices.as_posix(), "source_sha256": digest,
        "rows": len(companies), "companies": int(companies.ticker.nunique()),
        "sessions": len(sessions), "feature_columns": FEATURE_COLUMNS,
        "reference_universe": UNIVERSE, "minimum_active_peers": 45,
        "validation_start": VALIDATION_START, "reused_test_start": TEST_START,
        "split_warning": "Nominal dates only: outcomes and boundary purging not yet applied.",
        "decision_time": "After session t closes; earliest execution next observed session.",
        "missingness": companies[FEATURE_COLUMNS].isna().sum().astype(int).to_dict(),
        "complete_feature_rows": int(companies.features_complete.sum()),
        "active_peer_counts": {str(k): int(v) for k, v in companies.groupby("session_date").active_peer_count.first().value_counts().items()},
        "code_sha256": {p: sha256(p) for p in ["src/features/build_dataset.py", "src/features/market.py"]},
    }
    out.mkdir(parents=True, exist_ok=False)
    destination = out / "market_features.csv"
    companies.to_csv(destination, index=False)
    metadata["output_sha256"] = sha256(destination)
    (out / "features_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return destination, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", default=DEFAULT_PRICES, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--expected-sha256", default=SELECTED_HASH)
    args = parser.parse_args()
    destination, metadata = build_dataset(args.prices, args.output_dir, args.expected_sha256)
    print(json.dumps({"output": str(destination), "rows": metadata["rows"], "complete_feature_rows": metadata["complete_feature_rows"]}, indent=2))
