"""Predeclared Phase 6.9 features available after session ``t`` closes."""

from __future__ import annotations

import numpy as np
import pandas as pd


CROSS_SECTIONAL_FEATURES = [
    "return_5d_peer_rank",
    "momentum_20d_peer_rank",
    "momentum_60d_peer_rank",
]
MARKET_REGIME_FEATURES = [
    "spy_volatility_20d",
    "spy_drawdown_60d",
    "spy_price_to_sma50",
]
EXPANSION_FEATURE_COLUMNS = CROSS_SECTIONAL_FEATURES + MARKET_REGIME_FEATURES
EXPANSION_GROUPS = {
    "cross_sectional_relative_strength": CROSS_SECTIONAL_FEATURES,
    "market_regime": MARKET_REGIME_FEATURES,
}
MINIMUM_ACTIVE_PEERS = 45


def _peer_percentile_rank(
    values: pd.Series,
    dates: pd.Series,
    eligible: pd.Series,
) -> pd.Series:
    """Average-tie peer rank scaled to [0, 1] using only same-date rows."""

    available = pd.to_numeric(values, errors="coerce").where(eligible)
    counts = available.groupby(dates).transform("count")
    positions = available.groupby(dates).rank(method="average", ascending=True)
    percentile = (positions - 1) / (counts - 1)
    return percentile.where(counts.ge(MINIMUM_ACTIVE_PEERS))


def build_phase6_expansion_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the six frozen expansion features aligned to ``frame`` rows.

    The function reads only current or trailing market fields. Peer ranks use
    stocks available on the same session. SPY regime values are calculated
    once per session and then mapped back to company rows.
    """

    required = {
        "ticker",
        "session_date",
        "volume",
        "active_peer_count",
        "activity_quorum_met",
        "spy_return",
        "momentum_5d",
        "momentum_20d",
        "momentum_60d",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing Phase 6.9 inputs: {sorted(missing)}")
    if frame.empty or frame.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Expansion input must have unique nonempty ticker/date rows")
    dates = pd.to_datetime(frame["session_date"], errors="raise")
    if dates.isna().any() or frame[["ticker", "session_date"]].isna().any().any():
        raise ValueError("Expansion input has an invalid row key")
    volumes = pd.to_numeric(frame["volume"], errors="coerce")
    if volumes.isna().any() or volumes.lt(0).any():
        raise ValueError("Expansion input has invalid volume")

    active = (
        volumes.gt(0)
        & frame["activity_quorum_met"].eq(True)
        & pd.to_numeric(frame["active_peer_count"], errors="coerce").ge(
            MINIMUM_ACTIVE_PEERS
        )
    )
    result = pd.DataFrame(index=frame.index)
    result["return_5d_peer_rank"] = _peer_percentile_rank(
        frame["momentum_5d"], frame["session_date"], active
    )
    result["momentum_20d_peer_rank"] = _peer_percentile_rank(
        frame["momentum_20d"], frame["session_date"], active
    )
    result["momentum_60d_peer_rank"] = _peer_percentile_rank(
        frame["momentum_60d"], frame["session_date"], active
    )

    benchmark = pd.DataFrame(
        {
            "date": dates,
            "spy_return": pd.to_numeric(frame["spy_return"], errors="coerce"),
        }
    )
    if benchmark.groupby("date")["spy_return"].nunique(dropna=True).gt(1).any():
        raise ValueError("Conflicting SPY returns on one session")
    sessions = pd.DatetimeIndex(sorted(dates.unique()))
    spy_return = benchmark.groupby("date")["spy_return"].first().reindex(sessions)
    first_observed = spy_return.first_valid_index()
    if first_observed is None or spy_return.loc[first_observed:].isna().any():
        raise ValueError("SPY return history has a gap after its first observation")

    spy_index = (1 + spy_return.fillna(0.0)).cumprod()
    regime = pd.DataFrame(index=sessions)
    regime["spy_volatility_20d"] = (
        spy_return.rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252)
    )
    regime["spy_drawdown_60d"] = (
        spy_index / spy_index.rolling(60, min_periods=60).max() - 1
    )
    regime["spy_price_to_sma50"] = (
        spy_index / spy_index.rolling(50, min_periods=50).mean() - 1
    )
    for column in MARKET_REGIME_FEATURES:
        result[column] = dates.map(regime[column]).to_numpy()

    result = result[EXPANSION_FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return result.reset_index(drop=True)
