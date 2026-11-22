# Phase 6 Feature-Ablation Conclusion

## Purpose

Phase 6 checked whether each existing group of market features helps the
return model or the risk model. It used four time-ordered development periods.
For each group, it compared the full 14-feature market model against the same
model with that group removed. The model used for these comparisons was
HistGradientBoosting.

This is development research evidence. It is not a final accuracy claim, a
trading result, a portfolio result, or an untouched-test result.

## Results

| Feature group | Return decision | Return mean change | Folds helped | Risk decision | Risk mean change | Folds helped |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Momentum | Reject | -0.00621 | 1 / 4 | Inconclusive | +0.00418 | 2 / 4 |
| Volatility | Reject | -0.01624 | 1 / 4 | Retain | +0.02229 | 4 / 4 |
| Downside/trend | Inconclusive | +0.00156 | 2 / 4 | Retain | +0.00396 | 3 / 4 |
| Market-relative (SPY) | Retain | +0.01227 | 3 / 4 | Reject | -0.00475 | 1 / 4 |
| Volume | Retain | +0.00192 | 3 / 4 | Retain | +0.00137 | 4 / 4 |

For risk, retained groups also passed the extra safety checks. Volatility,
downside/trend, and volume improved High-risk recall and reduced the serious
mistake of predicting Low risk when the real future result was High risk.
Market-relative features failed those risk safety checks: High-risk recall fell
and there were 234 more High-predicted-Low errors.

## Frozen development candidates

The versioned setting is
`configs/phase6_feature_freeze_v1.json`.

### Return candidate

- `volume_ratio_20d`
- `spy_momentum_20d`
- `excess_momentum_20d`
- `market_beta_60d`

Momentum and volatility are excluded because they were rejected for return.
The downside/trend group is not included in this minimal candidate because its
result was inconclusive, not because it was proven harmful.

### Risk candidate

- `volatility_20d`, `volatility_60d`
- `return_1d`, `downside_dev_20d`, `drawdown_from_peak_60d`
- `price_to_sma20`, `price_to_sma50`
- `volume_ratio_20d`

Market-relative features are excluded because they were rejected for risk.
Momentum is not included in the minimal candidate because its risk result was
inconclusive.

## Important limitation

The two frozen lists were assembled from individual leave-one-group-out tests.
Their exact smaller combinations were **not** refit during Phase 6. Therefore
they are fixed candidates for the next controlled evaluation stage, not proof
that the smaller combinations have already achieved the table's scores.

No SEC fundamental field is included. Phase 6.10 did not approve financial
features, so the market-plus-fundamentals comparison in Step 6.11 was blocked.

Volume uses Alpaca IEX-feed volume, not consolidated SIP market volume. The
market-relative group is aligned to daily SPY data after the session close;
exact intraday availability cannot be proven because the source has no bar
availability timestamp.

## Evidence identities

| Evidence | SHA-256 |
| --- | --- |
| Phase 6 dataset | `3373211ab40f218413818575e8ec04654e76c12feeedb7e148e0c02cc98a5c0f` |
| Chronological protocol | `764f988c93b537a18d7584c5847b7d8a1e588356a29c894bc5443992d2901c60` |
| Momentum report | `74062c9f29bec20b553a15d63d4e7ebe6e224541c61555f64af072bc5f46b8347` |
| Volatility report | `3d63089b35e627951da1c1f184f8284301651056309dd56d04ef1b6a6f3edc3b` |
| Downside/trend report | `95828b67118708311f46e10b9653335e57c951b3849dc5c56648d9782cf6ab95` |
| Market-relative report | `6b488e3d869cd647a6599e5e5c0814acacbb4135e994aa95b1921e69fe23826c` |
| Volume report | `085723ff7a1305030d1d35745f52c1f384e65470e7ecf9df4d19bbac76cf21cf` |

## Next gate

Phase 7 may evaluate only the exact frozen candidates. It must use time-ordered
training-side validation, keep the 2024-2025 reused test period out of feature
selection, and must not silently add fundamentals or new market features.
