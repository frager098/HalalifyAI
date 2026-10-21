"""Market features available after the current session closes.

All windows are calculated on a shared session index. Missing bars stay missing,
so a rolling window cannot silently jump across an absent trading session.
"""

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "return_1d", "momentum_5d", "momentum_20d", "momentum_60d",
    "volatility_20d", "volatility_60d", "downside_dev_20d",
    "drawdown_from_peak_60d", "price_to_sma20", "price_to_sma50",
    "volume_ratio_20d", "spy_momentum_20d", "excess_momentum_20d",
    "market_beta_60d",
]


def build_market_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return features aligned to input rows without changing their order.

    `spy_return` is the benchmark's same-session return, already present in
    the existing modeling table. No future target or split column is read.
    """
    required = {"ticker", "session_date", "adjusted_close", "volume", "spy_return"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing market inputs: {sorted(missing)}")
    if frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/session_date rows")
    if frame[["ticker", "session_date"]].isna().any().any():
        raise ValueError("Ticker and session_date must be present")
    dates = pd.to_datetime(frame["session_date"], errors="raise")
    if dates.isna().any():
        raise ValueError("Invalid session_date")
    prices = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    volumes = pd.to_numeric(frame["volume"], errors="coerce")
    if ((prices <= 0) | (volumes < 0)).any():
        raise ValueError("Adjusted close must be positive and volume nonnegative")

    sessions = pd.DatetimeIndex(sorted(dates.unique()))
    bench = pd.DataFrame({"date": dates, "ret": pd.to_numeric(frame["spy_return"], errors="coerce")})
    # A benchmark return is repeated for each stock on a session; disagreements
    # would make the market features depend on row ordering.
    if bench.groupby("date")["ret"].nunique(dropna=True).gt(1).any():
        raise ValueError("Conflicting SPY returns for one session")
    spy = bench.groupby("date")["ret"].first().reindex(sessions)
    spy_growth = (1 + spy).rolling(20, min_periods=20).apply(np.prod, raw=True) - 1

    work = frame[["ticker", "session_date"]].copy()
    work["date"] = dates.to_numpy()
    work["price"] = prices.to_numpy()
    work["volume"] = volumes.to_numpy()
    work["row_id"] = np.arange(len(work))
    parts = []
    for _, group in work.groupby("ticker", sort=False):
        group = group.set_index("date").reindex(sessions)
        price = group["price"]
        volume = group["volume"]
        ret = price.pct_change(fill_method=None)
        out = pd.DataFrame(index=sessions)
        out["return_1d"] = ret
        for window in (5, 20, 60):
            out[f"momentum_{window}d"] = price / price.shift(window) - 1
        for window in (20, 60):
            out[f"volatility_{window}d"] = ret.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(252)
        out["downside_dev_20d"] = np.sqrt(
            ret.clip(upper=0).pow(2).rolling(20, min_periods=20).mean()
        ) * np.sqrt(252)
        out["drawdown_from_peak_60d"] = price / price.rolling(60, min_periods=60).max() - 1
        out["price_to_sma20"] = price / price.rolling(20, min_periods=20).mean() - 1
        out["price_to_sma50"] = price / price.rolling(50, min_periods=50).mean() - 1
        out["volume_ratio_20d"] = volume / volume.rolling(20, min_periods=20).mean()
        out["spy_momentum_20d"] = spy_growth
        out["excess_momentum_20d"] = out["momentum_20d"] - spy_growth
        out["market_beta_60d"] = (
            ret.rolling(60, min_periods=60).cov(spy)
            / spy.rolling(60, min_periods=60).var()
        )
        out["row_id"] = group["row_id"]
        parts.append(out.dropna(subset=["row_id"]))
    result = pd.concat(parts).set_index("row_id").sort_index()
    result.index = result.index.astype(int)
    return result[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
