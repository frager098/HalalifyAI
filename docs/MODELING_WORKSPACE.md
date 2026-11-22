# HalalifyAI modeling and cleaning workspace

The modeling dataset is in `data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/`:

- `model_dataset.csv`: price-based company rows with both risk targets and chronological splits.
- `targets_metadata.json`: target definitions, class thresholds, feature allowlist, splits and checksums.
- `README.md`: modeling usage notes.

Original benchmark snapshots are preserved in `data/raw/`. The original combined price input is preserved in `data/interim/` because the cleaner validates it against raw Alpaca responses. `SOURCE.json` records downloader provenance.

Current commands are modules: `python -m src.data_pipeline.validate_source_data --phase2`, `python -m src.data_pipeline.clean_source_data`, and `python -m src.legacy.target_generation.create_legacy_targets`. The last command builds legacy targets; the current modeling dataset is built by `src.target_engineering.build_modeling_dataset`. `requirements-cleaning.txt` supplies the exchange-calendar dependency. Use the commands in [CLEANING_README.md](CLEANING_README.md).

Phase 2 preserves the original inputs and adds `data/raw/alpaca/alpaca_sip_20261009T110617242394Z_restored_json_v1/`: all price pages match the original acquisition hashes after recovering compact JSON bytes. A completed market-only cleaning run and the exact eligible input are named in `reports/data_validation/v1/consolidated_review/phase2_report.json`. The full data decision and remaining limitations are in [DATA_REVIEW.md](DATA_REVIEW.md). SEC predictors remain excluded; original AAPL Company Facts integrity is unresolved.

See `CLEANING_README.md` for execution instructions. Both target columns must be excluded from model input features for every task. The source's unresolved corporate-action and historical identity checks still apply.

## Phase 6.2 recovery run — completed 2026-11-20

The old Git-ignored Phase 3–5 generated package was not available on this
computer. It was not replaced with an unverified table. For the inventory only,
a separately named recovery dataset was rebuilt from the preserved Alpaca source
and checked against a newly rebuilt Phase 4 protocol:

- Dataset: `data/processed/model_inputs/phase6_recovery_v1/market_features_and_labels.csv`
  — SHA-256 `3373211ab40f218413818575e8ec04654e76c12feeedb7e148e0c02cc98a5c0f`.
- Protocol: `reports/model_evaluation/phase6_recovery_v1/chronological_evaluation_protocol.json`
  — SHA-256 `764f988c93b537a18d7584c5847b7d8a1e588356a29c894bc5443992d2901c60`.
- Inventory: `reports/model_evaluation/phase6_recovery_v1/feature_inventory.json`
  and `.csv` — 14 approved market candidates and 42 explicitly excluded columns.

Run the verified recovery inventory with:

```powershell
.\.venv\Scripts\python.exe -m src.model_training.feature_ablation.feature_inventory `
  --recovery-dataset data/processed/model_inputs/phase6_recovery_v1/market_features_and_labels.csv `
  --recovery-metadata data/processed/model_inputs/phase6_recovery_v1/dataset_metadata.json `
  --recovery-protocol reports/model_evaluation/phase6_recovery_v1/chronological_evaluation_protocol.json `
  --output-json reports/model_evaluation/phase6_recovery_v1/feature_inventory.json `
  --output-csv reports/model_evaluation/phase6_recovery_v1/feature_inventory.csv
```

It checks the dataset, metadata and protocol hashes before it writes anything.
The output identifies 3 momentum, 2 volatility, 5 downside/trend, 3
market-relative and 1 volume candidate. It approves **no** fundamental features;
the SEC readiness gate remains required. This is a completed feature inventory,
not a new model result or a replacement for the unavailable old Phase 5 reports.

## Phase 6.3 recovery validation — completed 2026-11-21

Open `notebooks/phase6_recovery_validation.ipynb` in VS Code or Jupyter and
run its cells in order. It reads the completed Phase 6.2 recovery dataset,
metadata, time-based protocol, and feature inventory. It writes:

`reports/model_evaluation/phase6_recovery_v1/runner_validation.json`

A successful result says `validated`, lists 14 planned comparisons, and says
`model_fitting_performed: false`. This means the later comparison runner has
checked its safety rules: only approved inputs, the same ticker/date rows for a
comparison, training-only tuning, and time order. It is **not** a model result;
it cannot say that a feature improved return or risk prediction.

Before the notebook, run this focused code check from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_ablation_runner.py
```

The test passed: 8 focused checks completed successfully. The student then ran
the notebook, which created a `validated` local report with 14 planned
comparisons and `model_fitting_performed: false`. Its SHA-256 is
`6b73ce25cf9a7362fe850f5a8aa4aad32b947175deb5268405c97b3c1418e27`.
The generated validation report remains local because it is reproducible
evidence; the notebook, reusable runner, tests, and this instruction are
committed for teammates. This validates the runner only; Steps 6.4–6.8 are
where actual feature-comparison results will be generated.

## Phase 6.4 momentum comparison — prepared for student execution

Select the repository `.venv` kernel, then open and run
`notebooks/phase6_momentum_ablation.ipynb` from top to bottom. It performs the
first actual feature comparison: full approved market features versus the same
features without momentum. It runs return and risk separately, with the same
four chronological folds and inner-only tuning for both.

The run creates this local folder (it will refuse to overwrite it):

`reports/model_evaluation/phase6_recovery_v1/momentum_ablation/`

It contains four fold-result JSON files and `momentum_ablation_summary.json`.
The summary displays whether momentum is **retain**, **reject**, or
**inconclusive** for each task. `retain` does not mean a final investment model
is approved; it only means momentum helped this controlled development
comparison.

### Completed result — 2026-11-22

The student-run evidence summary has SHA-256
`74062c9f29bec20b553a15d63d4e7ebe6e224541c61555f64af072bc5f46b8347`.
Momentum is **rejected for return**: it improved only one of four folds and
reduced the mean same-date ranking score by 0.00621. Momentum is
**inconclusive for risk**: macro F1 increased by 0.00418 on average and risk
safety checks improved, but only two of four folds improved. All four paired
comparisons used identical rows and dates. These are development findings, not
untouched-test, portfolio, or trading results.

## Phase 6.5 volatility comparison — prepared for student execution

Select the repository `.venv` kernel, then run
`notebooks/phase6_volatility_ablation.ipynb` from top to bottom. This compares
all approved market features with the same feature set excluding the two
trailing-volatility inputs. It evaluates return ordering and risk classification
separately using the same four chronological folds.

The notebook creates this new local folder and refuses to overwrite it:

`reports/model_evaluation/phase6_recovery_v1/volatility_ablation/`

It produces four fold-result JSON files and `volatility_ablation_summary.json`.
The risk summary includes both High-risk recall and the severe error where a
High-risk outcome was predicted Low. No result is final until the generated
summary has been reviewed.

### Completed result — 2026-11-22

The student-run volatility summary has SHA-256
`3d63089b35e627951da1c1f184f8284301651056309dd56d04ef1b6a6f3edc3b`.
Volatility is **rejected for return** because it helped in only one of four
folds and removing it improved mean return ranking by 0.01624. Volatility is
**retained for risk**: macro F1 improved in all four folds by 0.02229 on
average, High-risk recall improved, and there were 529 fewer High outcomes
predicted Low.

## Phase 6.6 downside/trend comparison — prepared for student execution

Select the repository `.venv` kernel, then run
`notebooks/phase6_downside_trend_ablation.ipynb` from top to bottom. This
compares all approved market features with the same set excluding five related
inputs: one-day return, downside deviation, drawdown, and the two
price-to-moving-average ratios. It evaluates return ordering and risk
classification separately using the same four chronological folds.

The notebook creates this new local folder and refuses to overwrite it:

`reports/model_evaluation/phase6_recovery_v1/downside_trend_ablation/`

It produces four fold-result JSON files and
`downside_trend_ablation_summary.json`. The risk summary includes both
High-risk recall and the severe error where a High-risk outcome was predicted
Low. No result is final until the generated summary has been reviewed.

### Completed result — 2026-11-22

The student-run downside/trend summary has SHA-256
`95828b67118708311f46e10b9653335e57c951b3849dc5c56648d9782cf6ab95`.
The group is **inconclusive for return**: it improved the mean ranking score by
only 0.00156 and improved two of four folds. It is **retained for risk**:
macro F1 improved in three of four folds by 0.00396 on average, High-risk
recall improved, and there were 187 fewer High outcomes predicted Low.

## Phase 6.7 market-relative comparison — prepared for student execution

Select the repository `.venv` kernel, then run
`notebooks/phase6_market_relative_ablation.ipynb` from top to bottom. It first
checks daily SPY alignment, then compares all approved market features with the
same set excluding SPY momentum, excess momentum, and beta. It evaluates return
ordering and risk classification separately using the same four chronological
folds.

The notebook creates this new local folder and refuses to overwrite it:

`reports/model_evaluation/phase6_recovery_v1/market_relative_ablation/`

It produces four fold-result JSON files,
`market_relative_alignment.json`, and `market_relative_ablation_summary.json`.
The source has no exact intraday availability timestamp, so the report records
this as a daily after-close alignment check with a timing limitation.

## Phase 6.8 volume comparison — completed

Select the repository `.venv` kernel, then run
`notebooks/phase6_volume_ablation.ipynb` from top to bottom. It compares all
14 approved market features against the same set without the one volume feature
`volume_ratio_20d`. That feature means today's daily volume divided by the
company's average daily volume over today and the previous 19 sessions. Return
and risk are evaluated separately using the same four chronological folds.

The notebook creates this new local folder and refuses to overwrite it:

`reports/model_evaluation/phase6_recovery_v1/volume_ablation/`

It produces four fold-result JSON files and `volume_ablation_summary.json`.
The report states an important limitation: this historical volume came from
Alpaca's IEX feed, not the combined volume of all US exchanges (SIP). Therefore
the result can show whether this collected volume feature helps this project;
it cannot claim to measure whole-market trading volume. The same predeclared
retain/reject/inconclusive rule and extra risk safety checks from Steps 6.4–6.7
are used.

### Completed result

The student ran the notebook and generated the local report. **Keep volume for
both models.** For return, including volume raised the mean ranking score by
`+0.00192` and helped in 3 of 4 chronological folds. For risk, it raised macro
F1 by `+0.00137` in all 4 folds, raised High-risk recall by `0.00339`, and made
55 fewer serious High-risk-predicted-Low mistakes. The summary SHA-256 is
`085723ff7a1305030d1d35745f52c1f384e65470e7ecf9df4d19bbac76cf21cf`.

### Phase 6.7 completed result

The saved local report at
`reports/model_evaluation/phase6_recovery_v1/market_relative_ablation/market_relative_ablation_summary.json`
shows that the three SPY-based features are **retained for return**. They raised
the mean return ranking score by `+0.01227` and helped in 3 of 4 folds. They are
**rejected for risk**: average macro F1 fell by `-0.00475`, High-risk recall
fell by `0.02094`, and the model made 234 more serious mistakes where a future
High-risk outcome was predicted Low. No SPY-based feature was missing in any
fold row. The daily timing limitation remains: exact intraday source arrival is
not provable because `bar_available_at` is blank.

## Phase 6.9 new-market-feature review — completed

**Decision: do not add another market feature now.** This is an intentional
decision, not missing work. The completed results show that momentum and
volatility do not help the return task consistently; volatility and
downside/trend help the risk task. They do not identify one clear missing piece
that a new trailing feature is expected to fix. The Phase 6.7 market-relative
result gives different answers for return and risk; it does not point to a new
feature. The Phase 6.8 volume result retains the existing volume feature for
both tasks; it does not identify a justified new feature.

Adding more features merely to search for a better score would make the study
less fair. No extra code, notebook, model fitting, or parameter tuning was
created for this step. Reopen this decision only if later evidence identifies a
precise weakness, and write that proposed feature's formula,
lookback, availability time, and expected purpose before evaluating it.

## Phase 6.10 SEC fundamental readiness gate — completed, not passed

**No financial-company field may enter the model yet.** This is a safety
decision, not a failure of the market-feature work. The available SEC evidence
does not meet the project's requirements for reproducible historical model
features.

The earlier point-in-time review selected only assets, cash, and a same-filing
cash-to-assets ratio as research candidates. It kept them out of model training
because the AAPL SEC source was not verified and historical issuer identity and
as-filed snapshot vintage were unresolved. In the current checkout, the full
versioned SEC snapshot and its generated audit report are also absent, so that
review cannot be reproduced here. The raw SEC folder alone is not enough: it
lacks the matching full submission files and immutable manifest needed for the
50-company provenance check.

Therefore the approved Phase 6 fundamental feature list is **empty**. Debt,
revenue growth, profit margin, historical market capitalization, and filing age
are also excluded. Step 6.11 is blocked; it must not compare market-only data
with unverified fundamentals. A future retry needs a new complete immutable SEC
snapshot, a hash manifest, verified issuer identity, point-in-time filing
availability, amendment treatment, and explicit feature definitions.

## Phase 6.11 market-only versus fundamentals comparison — completed, blocked

There is no Phase 6.11 notebook or model result. This is correct: Step 6.10
approved **zero** financial-company fields, so a market-plus-fundamentals model
cannot be built honestly. The current valid benchmark is the market-only model
using its 14 approved market features.

Do not fill missing SEC values with zero, copy current financial values into
past dates, or use the research-only assets/cash panel as though it were
verified training data. After a future successful SEC gate, this comparison
must use the same ticker/date rows in both versions, report how many rows are
lost because of financial-data availability, use only information available
after each filing, and learn missing-value handling from the training period
only.
