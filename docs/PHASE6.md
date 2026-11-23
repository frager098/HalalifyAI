# Phase 6 — feature review, controlled expansion, and final freeze

## Current authority

This is the single canonical Phase 6 document. Current decisions use the exact
dataset and protocol from the student's Phase 5 execution. The friend's
`phase6_recovery_v1` experiment, `results/` folder,
`configs/phase6_feature_freeze_v1.json`, and their generated reports remain
historical evidence only. They do not control Phase 7.

The final machine-readable decision is
`configs/phase6_feature_freeze_v2.json`. Phase 7 handoff and execution rules are
in `docs/PHASE7_RUNBOOK.md` and `configs/phase7_handoff_v1.json`.

## Frozen lineage

- Phase 5 dataset:
  `data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv`
- Dataset SHA-256:
  `71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f`
- Metadata SHA-256:
  `b36ed46ac5a68b74130b26df8f20d965928c53d62467c163a214f8b37fd35ba9`
- Reproduced Phase 5 protocol SHA-256:
  `048d82ce2ed0bedde60bd5f6215303fa86ebdab31aae5b5c330f0947372859ff`
- Decision time: after session `t` closes; execution is no earlier than the
  next observed session.
- Development evaluation: four expanding chronological folds ending
  2024-06-28.
- Reused-test boundary: 2024-07-01. This period was excluded from Phase 6
  selection.

All feature comparisons used HistGradientBoosting with inner-validation tuning,
outer-training refitting, identical paired rows, training-outcome purging, and
fold-training risk cutoffs. The folds are development evidence, not an
untouched test.

## Exact-lineage continuation

The student ran the setup notebook followed by momentum, volatility,
downside/trend, market-relative, and volume comparisons. Reports are preserved
under `reports/model_evaluation/phase6_phase5_continuation_v1/`.

The predeclared rule was:

- retain only when the mean primary-metric difference is positive and at least
  three of four folds improve;
- reject when the mean is nonpositive and at least three folds are
  nonpositive;
- otherwise mark inconclusive; and
- for risk, a primary gain cannot be retained when mean High-risk recall falls
  or total High-to-Low errors increase.

Improving in most folds alone was not sufficient. Decisions apply to complete
feature groups, not individual columns.

| Existing group | Return decision | Mean change | Folds helped | Risk decision | Mean change | Folds helped |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Momentum | Inconclusive | -0.00499 | 3 / 4 | Inconclusive | +0.00022 | 1 / 4 |
| Volatility | Inconclusive | -0.00349 | 2 / 4 | **Retain** | +0.01443 | 4 / 4 |
| Downside/trend | Inconclusive | -0.00702 | 2 / 4 | **Retain** | +0.00326 | 3 / 4 |
| Market-relative | Inconclusive | +0.00665 | 2 / 4 | **Reject** | -0.00256 | 1 / 4 |
| Volume | **Reject** | -0.00241 | 1 / 4 | Inconclusive | +0.00127 | 2 / 4 |

Risk safety evidence supported the retained groups. Volatility changed mean
High-risk recall by `+0.00045` and produced 493 fewer High-to-Low errors.
Downside/trend changed recall by `+0.01416` and produced 225 fewer High-to-Low
errors.

### Continuation evidence identities

| Summary | SHA-256 |
| --- | --- |
| Momentum | `715a2d03bf58a2fb08bdef1e3d8438f8ffd38a13f55d36527f2c3c59ca0f7e48` |
| Volatility | `8431df9d0c3eef50768f6a07011c6e9daa7d120833174a097a3bf2968c308b16` |
| Downside/trend | `f9b427df9220d65f40d912b21092aa0b108fdaf8033c45fdbe5110d5b0a14916` |
| Market-relative | `26c020c1a2c987212846a5cdb9ea6cd7679b0823936d33c5913249f5b65e0c1d` |
| Volume | `0aec70ae1a820f7bde74fa2d8482172c26fb9b693983be3bbe1097d27c856d4b` |

These hashes still match the saved reports. The controlled expansion did not
overwrite them.

## Controlled Phase 6.9 expansion

The continuation identified a precise problem: no existing group passed the
return-retention rule. Six formulas were therefore frozen before fitting in
`configs/phase6_market_feature_expansion_v1.json`.

### Cross-sectional relative strength

For each active company on session `t`, ties receive average rank and the peer
percentile is `(rank - 1) / (peer_count - 1)`. At least 45 active peers are
required.

- `return_5d_peer_rank`: peer percentile of
  `adjusted_close(t) / adjusted_close(t-5) - 1`.
- `momentum_20d_peer_rank`: peer percentile of
  `adjusted_close(t) / adjusted_close(t-20) - 1`.
- `momentum_60d_peer_rank`: peer percentile of
  `adjusted_close(t) / adjusted_close(t-60) - 1`.

### SPY market regime

SPY daily returns through session `t` define a reconstructed index.

- `spy_volatility_20d`: sample standard deviation of the latest 20 SPY daily
  returns, multiplied by `sqrt(252)`.
- `spy_drawdown_60d`: reconstructed SPY index divided by its latest 60-session
  maximum, minus 1.
- `spy_price_to_sma50`: reconstructed SPY index divided by its latest
  50-session mean, minus 1.

All six features are available after the daily close. Exact minute-level source
arrival is not claimed.

### Separate dataset version

The expansion created, without overwriting Phase 5:

`data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv`

- Expanded dataset SHA-256:
  `99957129c288d90f63539577f707f0e04d9ad1be3a847e929b9e54e51e2ba9b0`
- Expanded metadata SHA-256:
  `0f1df79371f9fe45f09f7b8ddb576629ac744f01e51e3d2238c79dd7f8563f27`
- Expanded protocol SHA-256:
  `cc949ed87cda07a22693e4f1844475d2588078895cef6cd79f8dbaf103995060`
- Rows: 124,987, in the original ordered ticker/date layout.
- Eligible rows: 118,987 for return and 118,987 for risk.
- No eligible row is missing a new feature.

A post-run audit found CSV round-trip noise in one continuous return value
(`3.4e-21`) and one continuous volatility value (`4.4e-16`). No key, class,
same-date target rank, split, eligibility decision, fold membership, or risk
cutoff changed.

### Expansion results

Each group was compared as original 14 features versus the same rows with the
three new features added.

| New group | Return decision | Mean change | Folds helped | Risk decision | Mean change | Folds helped |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Cross-sectional relative strength | **Retain** | +0.00760 | 3 / 4 | **Reject** | -0.00117 | 1 / 4 |
| SPY market regime | Inconclusive | +0.00981 | 2 / 4 | Inconclusive | -0.00667 | 2 / 4 |

Cross-sectional relative strength increased return mean daily Spearman from
`0.00642` to `0.01402`. Its risk version produced 29 additional High-to-Low
errors despite improved mean High-risk recall. The market-regime risk
guardrails worsened: mean High-risk recall changed by `-0.00957` and
High-to-Low errors increased by 98. It remains inconclusive rather than rejected
because only two primary-metric folds were nonpositive under the frozen rule.

### Expansion evidence identities

| Evidence | SHA-256 |
| --- | --- |
| Validation | `4777f3e9d7aca48b2fd15833e474a33a46533f9bf2a691806396611865dbef7e` |
| Cross-sectional summary | `7032a0a0760634d660f511099da1a3853163cd1bdf3874a6421dc7fd5f935d59` |
| Market-regime summary | `cd6fb7288d5f923db831145147d0a524baae4a01e5dc2a2e05a35c4973e5d315` |

## Leakage and evaluation audit

The final audit independently confirmed:

- all 14 task/group comparisons used identical paired rows;
- all 56 fold pairs matched on inner/outer training and evaluation identities;
- all 16 task/fold roles were chronological;
- training target windows ended before evaluation began;
- risk cutoffs matched training-only quantiles;
- hyperparameters were selected on inner validation only;
- selected settings were refit on outer training before outer scoring;
- tree early stopping was disabled; and
- every development evaluation date preceded the reused-test boundary.

Peer ranks use same-session company information only after that session closes.
SPY regime features use only current and trailing returns. No direct look-ahead
leakage was found. Because Phase 6 used these folds for feature selection, its
scores are development evidence and cannot serve as a fresh generalization
estimate.

## SEC readiness gate

No SEC fundamental feature is approved. The required immutable Company Facts
and submissions snapshot, manifest, issuer-identity verification, historical
vintage checks, amendment handling, and validated concept/period semantics are
not available. Assets, cash, cash-to-assets, filing age, debt, revenue growth,
profit margin, and historical market capitalization remain excluded. No
market-plus-fundamentals result was fabricated.

## Final Phase 6 v2 freeze

### Return candidate

Return advances with the directly evaluated 17-feature candidate: the original
14 Phase 5 market features plus:

- `return_5d_peer_rank`
- `momentum_20d_peer_rank`
- `momentum_60d_peer_rank`

The three peer-rank columns were not tested alone. Keeping the original 14 does
not reclassify every original group as individually retained; it preserves the
exact baseline to which the retained group was added.

### Risk candidate

Risk advances with seven features from the two retained continuation groups:

- `volatility_20d`, `volatility_60d`
- `return_1d`, `downside_dev_20d`, `drawdown_from_peak_60d`
- `price_to_sma20`, `price_to_sma50`

This exact seven-feature combination was not refit in Phase 6. Phase 7 must
compare it with the original 14-feature risk comparator rather than assume it
wins.

## Limitations and next gate

- The current 50-stock universe introduces survivorship and selection bias.
- Twenty-session outcomes overlap; daily rows are not independent trials.
- Alpaca IEX volume is not consolidated SIP whole-market volume.
- Market features are available after the daily close; exact intraday delivery
  timestamps are absent.
- Phase 6 is not a Shariah-screened portfolio, trading, or untouched-test
  result.

Phase 7 may use only the v2 frozen candidates, original 14-feature comparators,
declared Logistic Regression and HistGradientBoosting families, and fixed
training-side budget. It must use the transferred Phase 6 artifacts rather than
build a different dataset. See `docs/PHASE7_RUNBOOK.md`.
