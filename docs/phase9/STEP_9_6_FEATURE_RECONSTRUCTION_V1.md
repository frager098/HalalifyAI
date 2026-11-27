# Phase 9.6 historical feature reconstruction

`src/model_training/phase9_feature_inference.py` implements `reconstruct_phase9_features(bars, decision_date, expected_tickers)`. Input is an after-close chronological panel with exactly `ticker`, `session_date`, `adjusted_close`, `volume`, and same-session `spy_return`. The caller supplies a verified ticker roster for that historical decision date; the function rejects a missing ticker rather than silently changing same-date peer ranks. The current frozen dataset supplies that roster for historical fixtures. A future API/provider integration must establish its own point-in-time roster; it must not assume today's 50 stocks were always active.

The function checks unique ticker/date keys, allowed tickers, finite positive prices, nonnegative volume, consistent SPY returns, consecutive XNYS sessions, at least 61 sessions, decision-date freshness, complete history for active peers, and 45–50 active peers. It rejects extra columns, including labels and future outcomes. It calls the existing frozen `build_market_features` and `build_phase6_expansion_features` formulas and returns only the approved return/risk feature union for the decision date. All feature calculations stop at that date; model fitting and predictions are outside this step.

Historical fixtures at **2016-03-31**, **2021-06-25**, and **2024-05-30** match the corresponding frozen Phase 6 modeling rows in ticker order and all 17 selected features, with `rtol=1e-10` and `atol=1e-12`. The 2016 fixture is the earliest eligible feature date: its 61-session history starts on 2016-01-04 and contains 49 stocks because LIN was not yet listed. The first source session has no prior SPY close, so its SPY return is undefined; this initial value is allowed, while every later missing SPY return is rejected. At 2024-05-30, the largest absolute difference observed was about `6e-15` (market beta). Ten focused tests pass, including duplicate, unknown, nonfinite, missing-session, missing-peer, extra-column, stale-date, and short-history rejection. Run:

```powershell
.\.venv-phases\Scripts\python.exe -m pytest tests/test_phase9_feature_inference.py -q -p no:cacheprovider
```

The data contract still requires the caller to know when the closing bar and SPY return became available; source provider arrival timestamps are missing. The function is an after-close historical reconstruction, not a live feed adapter, model evaluation, or Shariah screen. Step 9.7 will run the packages on these reconstructed features.
