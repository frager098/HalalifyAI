# Model evaluation history

This document preserves the sequence of feature experiments, chronological development evaluation, frozen choice, and saved-period check. Timestamped CSV and JSON outputs remain local under reports/generated/.

---

## Feature comparison and initial ranking


The saved baseline results remain in `notebooks/legacy/risk_modeling_baseline.ipynb` and
`notebooks/legacy/return_modeling_baseline.ipynb`. This experiment keeps their existing
targets and chronological split. It checks whether trailing market factors
help the three-class risk and return tasks, their continuous targets, and the
already saved SPY-relative return targets.

Run from the repository root:

```powershell
python -m src.legacy.model_experiments.compare_feature_sets
```

The command writes `validation_scores.csv` and `run_metadata.json` under a
new timestamped `reports/generated/` directory. It compares raw and factor
inputs on exactly the same eligible rows. The 60-session warmup is excluded
from both inputs. It does not score the test split or replace saved models.

### Result from 2026-10-19

The latest run is `reports/generated/legacy/modeling/feature_comparison_20261019T054537Z/`.
It uses 83,237 training rows and 17,850 validation rows from the preserved
dataset (SHA-256 `ad9b35d6be20564546312259bb75854c4de5c6c3d5a9e5034b7d56e46c9e8a58`).

| Target and metric | Raw inputs | Trailing factors |
| --- | ---: | ---: |
| Risk class, best macro F1 | 0.499 logistic | 0.595 boosted trees |
| Future volatility, best RÂ² | 0.107 boosted trees | 0.404 boosted trees |
| Return class, best macro F1 | 0.370 logistic | 0.367 boosted trees |
| Future return, best RÂ² | 0.002 Ridge | 0.006 Ridge |
| SPY-relative return class, best macro F1 | 0.352 logistic | 0.360 boosted trees |
| SPY-relative return, best RÂ² | 0.015 Ridge | -0.004 Ridge |

These are validation scores for this one chronological period, not new test
scores. The risk gains justify further checking. The return gains are tiny or
absent; changing model complexity alone is not supported by these results.

Read return macro F1 against the dummy predictor, and read return RÂ² and
daily cross-sectional rank correlation alongside the dummy regressor. Favor
a factor set only if it improves validation results consistently; a higher
score from one run is not evidence of a reliable investment strategy.

Next, audit price adjustment and historical identity flags. For return,
compare a simple momentum rank with learned ranks on nonoverlapping monthly
validation dates, using rank correlation and selected-stock forward returns;
this is a research experiment, not a change to the existing class contract.
Then add SEC features only after their filing availability and concept
semantics are validated. After choosing an approach using validation data,
freeze the experiment before any further test scoring. The baseline notebooks
already display test scores, so a genuinely fresh final estimate will need a
later forward holdout or a predeclared walk-forward protocol. A portfolio
backtest also needs an approved Shariah methodology and point-in-time
eligibility.

### Price audit and monthly ranking follow-up

Run the internal price audit and the validation-only monthly ranking study:

```powershell
python -m src.data_pipeline.audit_market_price_sources
python -m src.legacy.model_experiments.validate_monthly_rankings
```

The audit writes a JSON summary, ticker coverage and nine large-move review
rows under `reports/generated/price_audit_20261019T060306Z/`. The saved SIP
snapshot and modeling CSV checksums match their manifests; model prices match
the interim prices. All 124,987 model rows still carry unverified adjustment
and identity flags and lack a bar-availability timestamp. Independent
historical evidence is needed to resolve those items.

The ranking study writes `summary.csv`, `rebalance_details.csv` and metadata
under `reports/generated/legacy/modeling/monthly_rank_20261019T060359Z/`. It selects the
first eligible date of each complete validation month, then skips a date when
its 20-session target window would overlap the preceding selected window.
It compares the top 10 of the same 50 stocks using trailing momentum, raw
Ridge, factor Ridge and factor boosted trees.

| Validation ranking | Dates | Mean rank IC | Mean top-10 forward return | Positive spread vs universe |
| --- | ---: | ---: | ---: | ---: |
| 20-session momentum | 11 | 0.077 | 4.877% | 10 |
| Raw Ridge | 11 | 0.060 | 4.314% | 5 |
| Factor Ridge | 11 | 0.028 | 4.006% | 5 |
| Factor boosted trees | 11 | -0.092 | 3.697% | 5 |

The universe mean forward return was 2.974% on these dates. These are
research selection diagnostics, not cumulative portfolio returns. The small
number of dates, current-stock universe, missing Shariah screen and omitted
costs prevent a strategy-performance claim. Momentum is the benchmark to beat
in the next return experiment; no return model is selected yet.

---

## Walk forward development evaluation


Run `python -m src.legacy.model_experiments.run_walk_forward_evaluation` from the repository root. The
2026-10-20 run is saved under
`reports/generated/legacy/modeling/walk_forward_20261020T105443Z/`. It uses the preserved
modeling dataset with SHA-256
`ad9b35d6be20564546312259bb75854c4de5c6c3d5a9e5034b7d56e46c9e8a58`.
The saved test period starting 2024-07-01 is excluded from this run.

### Step 6: Shared-date folds and leakage checks

The code calls [scikit-learn's TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
on the **sorted unique market dates**, not on individual stock rows. Four
expanding-training folds each reserve 252 calendar sessions for evaluation.
`gap=20` removes 20 market sessions before each evaluation block. We also
check the **actual** `target_window_end`: training labels must end before the
evaluation start; evaluation labels must end by that block's last date and
before the saved test period. This trims approximately the last 20 signal
dates in each block. Thus a 20-session outcome never runs into the next
evaluation period. `folds.csv` records the dates, gap, row counts, threshold
values and passed leakage checks for each fold.

Both risk-volatility and return class tertiles are recalculated from that
fold's training rows only. Ridge's median imputer and scaler are fitted
inside a pipeline on training rows only. The boosted tree's imputer is fitted
the same way. Validation rows do not set thresholds or preprocessing values.
All comparisons use the same factor-ready ticker/date cohort within a fold.

| Fold | Evaluation dates | Common train rows | Common evaluation rows | Separated rebalances |
| --- | --- | ---: | ---: | ---: |
| 1 | 2020-06-26 to 2021-06-25 | 51,687 | 11,600 | 9 |
| 2 | 2021-06-28 to 2022-06-27 | 64,287 | 11,600 | 9 |
| 3 | 2022-06-28 to 2023-06-28 | 76,887 | 11,600 | 9 |
| 4 | 2023-06-29 to 2024-06-28 | 89,487 | 11,600 | 8 |

### Step 7: Add feature groups incrementally

1. Momentum and trailing volatility.
2. Add trend and downside measures.
3. Add SPY-relative market measures.
4. Add relative volume.

Risk uses the direct trailing 20-day volatility forecast as a no-fit
benchmark, then Ridge and a small histogram boosted tree. Return uses
Ridge and the same boosted tree, each compared directly with 20-day
momentum. All return rankings select the top 10 from the same 50 stocks on
the same separated rebalance dates. See `manifest.json` for columns and
fixed hyperparameters.

| Risk predictor | Mean RÂ² across folds | Fold SD of RÂ² | Mean MAE |
| --- | ---: | ---: | ---: |
| Trailing volatility 20d | 0.102 | 0.143 | 0.0882 |
| Ridge, groups 1â€“3 | 0.363 | 0.140 | 0.0755 |
| Boosted tree, groups 1â€“3 | 0.361 | 0.084 | 0.0743 |
| Ridge, groups 1â€“4 | 0.364 | 0.137 | 0.0756 |
| Boosted tree, groups 1â€“4 | 0.358 | 0.087 | 0.0743 |

Market-relative features improve average risk RÂ²; relative volume adds no
clear further benefit. Four periods are too few to treat small differences
between Ridge and boosted trees as conclusive. `per_fold_scores.csv` and
`class_reports.csv` contain every fold's regression metrics and Low/Medium/
High precision, recall, F1 and support. The class reports convert continuous
predictions using that fold's training-only boundaries.

| Return ranking | Mean fold rank IC | Mean fold top-10 minus universe return | Fold SD of spread | Fold wins vs momentum |
| --- | ---: | ---: | ---: | ---: |
| 20-day momentum | 0.040 | +0.781% | 1.042% | â€” |
| Best learned average: boosted tree, groups 1â€“3 | 0.000 | +0.565% | 0.894% | 1 of 4 |

These means give each fold equal weight; each fold has 8 or 9 rebalance dates.
Every learned configuration had a negative **paired** fold-average spread
relative to momentum. The boosted tree with groups 1â€“3 was closest at
âˆ’0.216 percentage points, with fold SD 1.509
percentage points. Its selected group beat momentum on 14 of 35 dates.
`return_vs_momentum_per_date.csv` shows the paired differences; the per-fold
and summary files show variation across periods. These fold SD values are
descriptive variation, not confidence intervals from independent trades.

The Low/Medium/High return class reports are also saved. Their weak macro F1
scores support keeping this as a ranking research exercise, rather than
choosing a return classifier from these runs.

### Interpretation limits

This uses the currently saved 50-stock universe, price data and after-close
signals. The selected-stock forward returns start at the already observed
close, so they are **selection diagnostics**, not executable portfolio
returns. No Shariah screen, transaction cost or next-session entry price is
applied. Source checksums, corporate-action verification and historical
issuer identity still require resolution. Earlier notebooks already exposed
the saved test scores; a genuinely untouched final estimate needs new future
data or a predeclared forward evaluation. Do not tune repeatedly to this
report and present the same periods as an independent final test.

---

## Frozen protocol


This protocol was selected from development folds saved in
`reports/generated/legacy/modeling/walk_forward_20261020T105443Z/`. The executable freeze
command records exact data, metadata, development-output and code hashes
before `evaluate` is allowed to read test labels.

### Chosen approach

- **Risk:** Ridge regression with alpha 100 on feature groups 1â€“3:
  momentum/trailing volatility, trend/downside and SPY-relative market
  measures. Compare with the no-fit trailing 20-day volatility forecast.
  The development averages favored this simple model on RÂ²; adding volume
  offered no clear benefit. Report MAE, RMSE, RÂ² and train-threshold class
  precision, recall and F1.
- **Return:** Keep 20-day momentum as the chosen ranking. Score the best
  development learned challenger, a 50-iteration histogram boosted tree on
  groups 1â€“3, on the same dates and stocks. Report rank IC, top-10 minus
  universe spread, the paired challenger-minus-momentum difference and
  per-date outcomes. This challenger was below momentum in development;
  it is retained to document whether that failure persists.
- **Training:** Use all factor-ready rows before 2024-07-01 whose forward
  20-session target ends before 2024-07-01. Fit imputers, scaler, models and
  Low/Medium/High thresholds only on those rows.
- **Evaluation:** Use the saved `dataset_split=test` rows, on which both
  targets and chosen features are present. Rebalance on the first eligible
  complete-universe date in each month, skipping overlapping 20-session
  holding windows. Select 10 of the same 50 stocks for each ranking.

### Status of the test period

The saved 2024-07-01 onward test scores appeared in baseline notebooks before
this freeze. Therefore this run is a **predeclared reused-test check**, not
an untouched final estimate. The local `.env` is empty and there is no saved
matching SIP market dataset after 2025-12-31. A new independent forward
evaluation needs a later verified snapshot before a final generalization
claim. Do not tune this protocol after reading the reused-test result and
call the same rows a blind test.

The SEC `cash` feature discussed earlier means company cash and cash
equivalents divided by total assets, from the same historical filing. It is
not a cash holding or portfolio allocation. This feature remains excluded
because its candidate panel has unresolved source/vintage checks.

---

## Saved period evaluation


**Status:** Predeclared reused-test check, **not** a fresh blind final estimate.
The frozen protocol was written at 2026-10-20 11:05:43 UTC before this run
read the saved test labels. Baseline notebooks had already displayed scores
from the same 2024â€“2025 test period. Results below therefore check a frozen
development choice but cannot independently establish generalization.

### Dataset and code identity

| Item | Version / evidence |
| --- | --- |
| Modeling dataset | `data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/model_dataset.csv` |
| Dataset SHA-256 | `ad9b35d6be20564546312259bb75854c4de5c6c3d5a9e5034b7d56e46c9e8a58` |
| Git HEAD | `99011019d133e9be051dc21e5752630f7eea3be4` (evaluation code was uncommitted; file hashes below identify it) |
| Frozen protocol | `reports/generated/legacy/modeling/final_protocol_20261020T110543Z/protocol.json`; SHA-256 `6c0b187717943d14f72fa372dd3bb910a6e77d6daf18fc76df91304edf70794a` |
| Evaluation code SHA-256 | `final_evaluation.py`: `8a7df0b34dfcdd7dea266e81027be1d0114e45fb1fa101b3fc1ea622bc0c0d13` |
| Feature code SHA-256 | `market.py`: `21927c63a4c2e9a8d6ba31d386230a7e25ebeee4c88ec061d96940cb174825fc` |
| Library versions | Python environment: pandas 3.0.6, NumPy 2.5.4, scikit-learn 1.9.1 |
| Results | `reports/generated/legacy/modeling/final_evaluation_20261020T110552Z/` |

The protocol also records the target metadata, development output and
walk-forward code hashes. The evaluator rejected changed inputs or code.
It fitted on 102,087 common feature-ready rows from 2016-03-31 to
2024-05-30, whose last label ended 2024-06-28. It scored 17,900 saved test
rows with signal dates 2024-07-01 to 2025-12-02 and complete labels through
2025-12-31. Thresholds and preprocessing were learned from training only.

### Frozen choice and its baselines

Risk choice: Ridge regression on the first three trailing feature groups,
against the direct trailing 20-day volatility forecast. Return choice:
20-day momentum. The strongest development learned challenger, a small
histogram boosted tree on the first three groups, was scored for comparison
without changing the frozen return choice. See
`docs/MODEL_EVALUATION.md` for the selection rationale.

#### Risk: gain over the agreed simple baseline

| Predictor | MAE | RMSE | RÂ² | Low/Medium/High macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Trailing 20-day volatility | 0.1103 | 0.1649 | âˆ’0.0404 | 0.496 |
| Frozen Ridge model | **0.0844** | **0.1284** | **0.3691** | **0.529** |

Ridge reduced MAE by 23.5% relative to the trailing-volatility baseline and
raised RÂ² by 0.409. The gain is on the same 17,900 rows. The macro F1 gain
is smaller, so the three-class risk output still has classification errors;
`class_reports.csv` gives precision, recall and support for every class.

#### Return: development failure and a reversed reused-test result

Thirty-five separated dates across four development folds favored momentum.
The boosted-tree challenger beat momentum in only one of four fold averages.
On the reused test period, the direction reversed:

| Ranking | Separated dates | Mean rank IC | Mean top-10 return | Mean universe return | Top-10 minus universe |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen 20-day momentum | 13 | 0.007 | 1.875% | 2.518% | **âˆ’0.642%** |
| Boosted-tree challenger | 13 | 0.073 | 3.884% | 2.518% | **+1.366%** |

The challenger beat momentum on 10 of 13 paired dates. Its mean spread was
2.008 percentage points higher on these dates; the paired date-to-date
standard deviation was 3.344 percentage points, with a range from âˆ’4.106
to +6.916 points. This reversal shows that the return comparison changes
across market periods. It does **not** justify retroactively choosing the
challenger from the reused test. The challenger's return-class macro F1 was
only 0.201 using training-derived class thresholds. Per-date holdings and
spreads are in `rebalance_details.csv` and `return_vs_momentum.csv`.

### Practical conclusion and remaining gate

The risk model has a reproducible improvement over its simple baseline on
this reused test. Return ranking remains unsettled: momentum won the
development comparison, while the learned challenger won the reused test.
The frozen choice remains momentum until a genuinely later forward period
can evaluate both without tuning on it.

No matching SIP dataset after 2025-12-31 is saved locally, and the local
Alpaca `.env` contains no credentials. A new verified forward snapshot is
needed for a cleaner final estimate. The existing data still has unresolved
raw-file checksums, corporate actions and historical issuer identity. The
SEC cash-to-assets candidate was excluded; **cash** here means a company's
reported cash and cash equivalents, not portfolio cash. The ranking returns
start from a known closing price and omit Shariah screening, next-session
execution, transaction costs and survivorship changes. They are research
selection diagnostics, not an executable portfolio backtest.




