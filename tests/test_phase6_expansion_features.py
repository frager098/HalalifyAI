import numpy as np
import pandas as pd
import pytest

from src.feature_engineering.phase6_expansion_features import (
    CROSS_SECTIONAL_FEATURES,
    MARKET_REGIME_FEATURES,
    build_phase6_expansion_features,
)


def _market_frame(sessions=70, tickers=50):
    dates = pd.date_range("2020-01-02", periods=sessions, freq="B")
    rows = []
    for day, date in enumerate(dates):
        spy_return = np.nan if day == 0 else 0.001 + (day % 5) * 0.0001
        for ticker_number in range(tickers):
            rows.append(
                {
                    "ticker": f"T{ticker_number:02d}",
                    "session_date": date.strftime("%Y-%m-%d"),
                    "volume": 1000 + ticker_number,
                    "active_peer_count": tickers,
                    "activity_quorum_met": tickers >= 45,
                    "spy_return": spy_return,
                    "momentum_5d": ticker_number / 100 + day / 10_000,
                    "momentum_20d": ticker_number / 80 + day / 10_000,
                    "momentum_60d": ticker_number / 60 + day / 10_000,
                }
            )
    return pd.DataFrame(rows)


def test_peer_rank_formula_and_average_ties():
    frame = _market_frame(sessions=60)
    last = frame["session_date"].eq(frame["session_date"].max())
    # Two equal lowest values receive average rank 1.5, or 0.5 / 49.
    frame.loc[last & frame["ticker"].isin(["T00", "T01"]), "momentum_5d"] = -1

    result = build_phase6_expansion_features(frame)
    last_result = result.loc[last.to_numpy(), "return_5d_peer_rank"].reset_index(drop=True)

    assert last_result.iloc[0] == pytest.approx(0.5 / 49)
    assert last_result.iloc[1] == pytest.approx(0.5 / 49)
    assert last_result.iloc[-1] == pytest.approx(1.0)
    assert last_result.between(0, 1).all()


def test_spy_regime_formulas_match_manual_trailing_calculation():
    frame = _market_frame(sessions=70)
    result = build_phase6_expansion_features(frame)
    one_per_day = frame.drop_duplicates("session_date").reset_index(drop=True)
    returns = one_per_day["spy_return"]
    index = (1 + returns.fillna(0)).cumprod()
    final_rows = frame["session_date"].eq(frame["session_date"].max())
    actual = result.loc[final_rows.to_numpy()].iloc[0]

    assert actual["spy_volatility_20d"] == pytest.approx(
        returns.tail(20).std(ddof=1) * np.sqrt(252)
    )
    assert actual["spy_drawdown_60d"] == pytest.approx(
        index.iloc[-1] / index.tail(60).max() - 1
    )
    assert actual["spy_price_to_sma50"] == pytest.approx(
        index.iloc[-1] / index.tail(50).mean() - 1
    )


def test_future_rows_cannot_change_past_features():
    complete = _market_frame(sessions=75)
    cutoff = sorted(complete["session_date"].unique())[69]
    past = complete.loc[complete["session_date"].le(cutoff)].reset_index(drop=True)

    past_result = build_phase6_expansion_features(past)
    complete_result = build_phase6_expansion_features(complete).iloc[: len(past)]

    pd.testing.assert_frame_equal(past_result, complete_result.reset_index(drop=True))


def test_availability_quorum_and_missingness_are_fail_closed():
    too_few_peers = _market_frame(sessions=70, tickers=44)
    result = build_phase6_expansion_features(too_few_peers)
    assert result[CROSS_SECTIONAL_FEATURES].isna().all().all()
    assert result.loc[result.index[-1], MARKET_REGIME_FEATURES].notna().all()

    conflicting = _market_frame(sessions=70)
    second_session = conflicting["session_date"].unique()[1]
    conflicting.loc[
        conflicting["session_date"].eq(second_session) & conflicting["ticker"].eq("T01"),
        "spy_return",
    ] = 0.25
    with pytest.raises(ValueError, match="Conflicting SPY returns"):
        build_phase6_expansion_features(conflicting)

    gap = _market_frame(sessions=70)
    gap.loc[gap["session_date"].eq(gap["session_date"].unique()[30]), "spy_return"] = np.nan
    with pytest.raises(ValueError, match="history has a gap"):
        build_phase6_expansion_features(gap)

