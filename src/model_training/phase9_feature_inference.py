"""Rebuild frozen Phase 9 market features from an after-close historical panel."""

from __future__ import annotations

import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

from src.feature_engineering.market_features import build_market_features
from src.feature_engineering.phase6_expansion_features import build_phase6_expansion_features


REQUIRED = {"ticker", "session_date", "adjusted_close", "volume", "spy_return"}


def reconstruct_phase9_features(
    bars: pd.DataFrame,
    decision_date: str,
    expected_tickers: set[str],
    contract_path: Path = Path("configs/phase9_inference_contract_v1.json"),
    metadata_path: Path = Path("data/processed/model_inputs/phase6_expanded_features_v1/dataset_metadata.json"),
) -> pd.DataFrame:
    """Return one feature row per active peer at the last supplied session.

    Inputs contain only stock bars and aligned same-session SPY returns. The
    caller must invoke this after that session's close; no future row is read.
    """
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValueError("A nonempty daily stock panel is required")
    if set(bars.columns) != REQUIRED:
        raise ValueError(f"Expected exactly these market columns: {sorted(REQUIRED)}")
    if bars.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/session_date rows")
    if bars[list(REQUIRED - {"spy_return"})].isna().any().any():
        raise ValueError("Missing ticker, session, price, or volume")
    try:
        dates = pd.to_datetime(bars.session_date, format="%Y-%m-%d", errors="raise")
        decision = pd.Timestamp(decision_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid decision or session date") from exc
    if (dates.dt.strftime("%Y-%m-%d") != bars.session_date).any() or decision.strftime("%Y-%m-%d") != decision_date:
        raise ValueError("Session and decision dates must use YYYY-MM-DD")
    if dates.max() != decision or dates.min() > decision or not dates.is_monotonic_increasing:
        raise ValueError("Bars must end on the decision date in chronological order")
    if not set(bars.ticker).issubset(set(metadata["reference_universe"])):
        raise ValueError("Unknown or unsupported ticker")
    if not expected_tickers or not set(expected_tickers).issubset(set(metadata["reference_universe"])):
        raise ValueError("A verified expected ticker roster is required")
    prices = pd.to_numeric(bars.adjusted_close, errors="coerce")
    volumes = pd.to_numeric(bars.volume, errors="coerce")
    spy = pd.to_numeric(bars.spy_return, errors="coerce")
    # The first session of the entire source has no prior SPY close, so its
    # return is undefined. The 61-session feature window starts using SPY
    # returns on the next session; later missing values are never permitted.
    first_session = dates.min()
    if spy.loc[dates.ne(first_session)].isna().any():
        raise ValueError("Missing same-date SPY return after the first session")
    if (not np.isfinite(prices).all() or not np.isfinite(volumes).all()
            or not np.isfinite(spy.fillna(0)).all() or (prices <= 0).any()
            or (volumes < 0).any() or (spy <= -1).any()):
        raise ValueError("Nonfinite or invalid market input")
    benchmark = bars.assign(spy_return=spy).groupby("session_date").spy_return.nunique()
    if benchmark.gt(1).any():
        raise ValueError("Conflicting same-date SPY returns")
    sessions = pd.DatetimeIndex(sorted(dates.unique()))
    calendar = xc.get_calendar("XNYS", start=sessions.min() - pd.Timedelta(days=10),
                               end=decision + pd.Timedelta(days=10))
    expected_sessions = calendar.sessions_in_range(sessions.min(), decision).tz_localize(None)
    if not sessions.equals(expected_sessions) or len(sessions) < contract["inference_input"]["minimum_consecutive_sessions_including_decision_date"]:
        raise ValueError("Missing exchange sessions or insufficient rolling history")
    current = bars.session_date.eq(decision_date)
    peers = bars.loc[current & volumes.gt(0), "ticker"]
    peer_count = peers.nunique()
    if set(bars.loc[current, "ticker"]) != set(expected_tickers):
        raise ValueError("Incomplete decision-date ticker roster")
    if not (contract["inference_input"]["minimum_active_peers_on_decision_date"]
            <= peer_count <= contract["inference_input"]["maximum_active_peers_on_decision_date"]):
        raise ValueError("Incomplete decision-date peer group")
    # Every returned ticker needs the entire 61-session price history. This
    # rejects gaps rather than letting a rolling window jump over missing bars.
    # A later-listed company need not exist throughout an arbitrarily long
    # supplied panel; only the latest 61 sessions feed these frozen features.
    window = bars.loc[bars.session_date.isin(sessions[-61:].strftime("%Y-%m-%d"))].copy()
    counts = window.groupby("ticker").session_date.nunique()
    if any(counts[ticker] < 61 for ticker in peers):
        raise ValueError("Incomplete rolling history for an active peer")
    frame = window.reset_index(drop=True)
    frame["adjusted_close"] = pd.to_numeric(frame.adjusted_close).to_numpy()
    frame["volume"] = pd.to_numeric(frame.volume).to_numpy()
    frame["spy_return"] = pd.to_numeric(frame.spy_return).to_numpy()
    frame["active_peer_count"] = frame.session_date.map(
        frame.loc[frame.volume.gt(0)].groupby("session_date").ticker.nunique()
    ).fillna(0).astype(int)
    frame["activity_quorum_met"] = frame.active_peer_count.ge(
        contract["inference_input"]["minimum_active_peers_on_decision_date"]
    )
    market = build_market_features(frame)
    expanded = build_phase6_expansion_features(pd.concat([frame, market], axis=1))
    final = pd.concat([frame[["ticker", "session_date", "volume"]], market, expanded], axis=1)
    final = final.loc[final.session_date.eq(decision_date) & final.volume.gt(0)].copy()
    feature_order = list(dict.fromkeys(contract["return"]["feature_order"] + contract["risk"]["feature_order"]))
    result = final[["ticker", "session_date", *feature_order]].sort_values("ticker").reset_index(drop=True)
    if len(result) != peer_count or not np.isfinite(result[feature_order].to_numpy(dtype=float)).all():
        raise ValueError("Incomplete selected features or peer inputs")
    return result
