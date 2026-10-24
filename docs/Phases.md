# HalalifyAI model development phases

This roadmap covers the research prototype for U.S. equities. Its goal is to find risk and return models that work reliably on later data and support an explainable, Shariah-compliant portfolio. No accuracy, return, or compliance result is guaranteed by this plan.

The current [model evaluation](MODEL_EVALUATION.md) provides a promising Ridge risk benchmark. Learned return models have not consistently beaten 20-day momentum. The saved 2024–2025 test labels were viewed in earlier notebooks, so that period cannot serve as a fresh blind test. The current [data review](DATA_REVIEW.md) records source-integrity, corporate-action, and historical-identity issues.

The [approved phase 1 specification](Approved%20phases%20specifications.md) sets peer-relative return classification and training-derived volatility classes for experiments. Existing absolute-return, SPY-relative, and numerical-volatility results remain named benchmarks.

## Phase 1 — Define the prediction tasks and selection rules

- Keep separate return and risk models with a 20-trading-session horizon and predictions made after session **t** closes.
- For the new return task, classify each eligible stock's future return as Lower, Middle, or Higher **relative to other eligible stocks on the same date**. Evaluate ordering across stocks as the primary stock-selection objective. Compare class quality with macro F1, per-class precision and recall, ordinal error, and a confusion matrix. Where a classifier supplies probabilities, its proposed ranking score is `P(Higher) - P(Lower)`.
- For risk, retain future annualized realized volatility as the target quantity. Define Low, Medium, and High using the pooled training outcomes' 1/3 and 2/3 quantiles. Freeze the boundaries for each fitted model or chronological fold. Make macro F1 primary and report High-risk recall, severe underestimation, ordinal error, and probability quality.
- Preserve existing absolute-return regression and classes, SPY-relative results, numerical risk forecasts, and 20-day momentum as comparisons. Report numerical errors for numerical models, but judge stock selection with ranking measures on the same dates and stocks.
- Record how eligible stocks, ties, missing future outcomes, class boundaries, prediction timing, and model selection will work. Define all choices before examining results from a new evaluation period.
- Keep user risk preference in later portfolio construction. The meaning of a model's classes should stay stable for a given model version.

**Exit evidence:** A versioned modeling specification with formulas, units, reference universe, label rules, baselines, primary metrics, and open decisions. Do not describe a rank score or class probability as a percentage return.

## Phase 2 — Repair and validate source data

Work through these steps in order. Mark a step complete only when its evidence is saved. A finding can be **resolved**, **excluded from the next dataset**, or **open with a documented limitation**; do not turn an open finding into a verified flag. Keep all original raw files and the existing modeling snapshot unchanged.

**2026-10-22 status:** All 14 steps have been executed with saved evidence and dispositions. The market-only research gate is open; SEC predictors remain excluded. The 18 price checksum mismatches were recovered to their exact original digests in a separate snapshot. Event magnitudes and complete historical identities remain unverified. See [the phase 2 data decision](DATA_REVIEW.md#phase-2-decision--2026-10-22) and `reports/generated/phase2_20261022T060900192314Z/phase2_report.json`. Checked boxes mean the stated review/evidence work is complete, including explicit exclusions and limitations; they do not mean every finding is resolved.

### Source inventory and integrity

- [x] **2.1 Identify the exact inputs.** List the versioned Alpaca SIP and SEC snapshot directories, their manifests, the interim price CSV, and the saved modeling CSV. Record request parameters and observed date coverage for each. **Done when:** one inventory names the files and versions used in every later check; the older IEX dataset is listed separately.
- [x] **2.2 Reproduce the integrity findings.** Recompute file hashes against both provider manifests, and verify the saved model CSV against its metadata. Start from the existing price audit and SEC panel reports. **Done when:** an expected-versus-actual hash table identifies every mismatch, including the previously reported 18 Alpaca pages and two AAPL SEC files, without changing their manifests.
- [x] **2.3 Check what the Alpaca mismatches mean.** Compare the affected raw pages to the normalized SIP price rows on ticker, date, split-adjusted values, fully adjusted values, and volume. Separate byte-only differences from value differences. **Done when:** every affected page has a recorded comparison result and any changed market rows are listed for review.
- [x] **2.4 Check the AAPL SEC files.** Compare the affected companyfacts and submissions files with any preserved trusted copy or a new separately versioned download. Check CIK, accessions, filing dates, concepts, and values relevant to the candidate panel. **Done when:** the mismatch is explained or AAPL remains excluded from SEC features with a recorded reason.
- [x] **2.5 Choose and verify the source version.** Recover matching original bytes if available, or collect a new immutable snapshot and generate its own manifest at collection time. Never overwrite the old snapshot or change old expected hashes merely to pass validation. **Done when:** the source version for further work is named, its hashes pass, and differences from the previous version are documented. If acquisition is unavailable, record the blocker and continue only with explicitly limited research checks.

### Market prices and historical identity

- [x] **2.6 Run the cleaner on verified inputs.** Reuse `src/data_pipeline/clean_source_data.py` and inspect its quarantine, coverage, review, and report files. Its recorded earlier run stopped at a checksum mismatch. **Done when:** a new run has a completed `report.json`, or the exact remaining failure is saved and assigned for resolution.
- [x] **2.7 Check trading-session coverage.** Compare each stock's dates with the reference sessions and its actual listing period. Record gaps, unexpected dates, and observed starts and ends, including LIN's later start. **Done when:** a per-ticker table explains each material coverage exception without claiming requested dates were received.
- [x] **2.8 Review large price moves.** Revisit the nine previously flagged moves above 25%, one event at a time, using the split and fully adjusted series and independent dated evidence where available. **Done when:** each event is classified as verified, unresolved, or excluded with its evidence; genuine moves are not automatically deleted.
- [x] **2.9 Review corporate-action differences.** Group the 92 previously flagged dates where the two price bases differ by over one percentage point. Work through groups in small batches, starting with the known GE, DHR, and HON events; reconcile split, dividend, and spin-off candidates with dated provider or issuer records. **Done when:** each batch has documented interpretations or explicit unverified flags; adjusted-return features and labels use one stated price convention.
- [x] **2.10 Build a dated ticker/issuer review.** Record current and historical identifiers, listing dates, ticker changes, and major reorganizations in batches of ten companies; start with META/FB, LIN, GE, DHR, HON, and the XOM SEC mapping exception. **Done when:** affected dates are mapped or flagged, and the current 50-stock selection and survivorship bias are documented. Do not infer a complete historical identity map from today's ticker lookup.
- [x] **2.11 Record signal availability.** State that features using session `t`'s close can be acted on no earlier than the next observed trading session. Keep missing provider delivery timestamps visibly missing. **Done when:** the timing rule and `bar_available_at` limitation are in the validation report; the close-to-close target is not described as an executable holding return.

### SEC semantics and phase exit

- [x] **2.12 Validate candidate SEC facts.** Check assets and cash one concept at a time for USD units, instant periods, 10-K/10-Q forms, filing/accession provenance, restatements, conflicts, and the conservative availability date. Confirm that `cash_to_assets` uses the same accession and period. **Done when:** accepted and quarantined facts are traceable to source filings and no market date receives a future filing.
- [x] **2.13 Keep unsupported fundamentals separate.** Review debt components, revenue durations, restricted cash, and receivables issuer by issuer before making ratios. Record which definitions and companies remain incomplete; do not fill historical gaps with current provider values. **Done when:** an approved candidate list and an unresolved-concepts list exist. Profit margin and market capitalization stay absent until their historical inputs are validated.
- [x] **2.14 Publish the phase 2 data decision.** Summarize source versions, coverage, checksums, exclusions, quality flags, the 50-stock universe limitation, and the exact rows/fields eligible for the next market-only experiment. State separately whether SEC features meet their point-in-time and provenance requirements. **Done when:** another developer can reproduce the report and tell which dataset can enter phase 3, which fields are research-only, and what evidence is still missing.

**Exit evidence:** An immutable selected source version, a reproducible validation report, an issue log with dispositions, and a clearly scoped market-data input for phase 3. SEC features require their own evidence before joining. Phase 2 may preserve documented limitations, but it must not label unresolved rows or fields as verified.

## Phase 3 — Build a saved feature and label dataset

Work through these steps in order. Keep the existing `data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/` snapshot and its `targets_metadata.json` unchanged; its labels are comparison benchmarks, not the approved phase 3 labels. Use the market-only `prices_clean.csv` selected by the [phase 2 decision](DATA_REVIEW.md#phase-2-decision--2026-10-22). SEC predictors remain excluded.

### Fix the dataset contract

- [x] **3.1 Confirm the input and output contract.** Read the phase 2 report to get the selected cleaned-price path and source hashes. List required source columns, one output row per `(ticker, session_date)`, intended output columns, and where a new versioned dataset will be saved. Keep SPY as a benchmark, not a modeled stock. **Done when:** a short schema and the exact selected source version are recorded before coding.
- [x] **3.2 Decide peer-group edge cases.** Record which company rows can receive a same-date return class, apply the approved minimum of 45 active reference stocks (90% of 50), including dates before LIN trades, how missing future outcomes affect a date, and a tie rule that does not split equal returns arbitrarily. Do not silently change the approved 50-stock reference universe. **Done when:** the rule is approved and can be expressed as deterministic tests; unresolved dates can remain unlabeled.
- [x] **3.3 Define the phase 3 split and label contract.** Record the chronological training dates used to derive the risk quantiles, the development split fields to save, the actual 20-session target end date, class names/codes, and the next-session signal-timing convention. Treat these as dataset-version definitions; phase 4 must still define and check each evaluation fold and refit risk boundaries using that fold's training rows. **Done when:** each saved label can be traced to its dates and, for risk, its training-only boundaries.

### Build the market-only table

- [x] **3.4 Add one reproducible build command.** Create a focused entry point that accepts the selected cleaned-price file and writes to a new versioned directory. Refuse duplicate ticker/date keys, invalid dates or prices, missing required columns, and an existing output directory. **Done when:** a single documented command builds a new table without modifying raw files or the older modeling snapshot.
- [x] **3.5 Calculate historical market features.** Reuse [`src/feature_engineering/market_features.py`](../src/feature_engineering/market_features.py) on the selected company rows and SPY benchmark. Keep the provider all-adjusted close convention for returns; use only sessions through `t` and leave incomplete rolling windows missing. Preserve input keys and row order when attaching features. **Done when:** each output feature aligns with its original ticker/date and no earlier row changes if later prices are altered.
- [x] **3.6 Calculate continuous 20-session outcomes.** For each company, calculate adjusted-close return from `t` to `t+20` and annualized sample volatility from returns `t+1` through `t+20` on the shared session calendar. Save the actual target-window end date. A missing bar anywhere in a required future window leaves the affected outcome missing. **Done when:** hand-checked windows, gaps, and final 20 sessions have the expected values or missing markers.
- [x] **3.7 Assign same-date return classes.** Apply the approved Lower/Middle/Higher rule to future returns only after step 3.2 has a recorded policy. Save peer counts and an explicit reason for dates or rows left unlabeled; keep continuous returns available for preserved numerical benchmarks. **Done when:** complete eligible dates produce reproducible classes and equal returns follow the recorded tie rule.
- [x] **3.8 Assign fixed risk classes.** Compute the 1/3 and 2/3 quantiles from eligible training outcomes only, save both numerical boundaries, then apply them unchanged to later rows. Keep the continuous volatility target for numerical risk benchmarks. **Done when:** changing validation or later outcomes cannot change the boundaries or earlier classes.
- [x] **3.9 Attach split, quality, and provenance fields.** Save the dataset split or eligibility status, `target_window_end`, selected source version, price-quality flags, and signal-availability limitations. Do not turn phase 2's unresolved corporate-action or historical-identity findings into verified flags. **Done when:** every excluded or unlabeled row has a traceable reason and the output never presents close-`t` target returns as executable trades.

### Verify and publish

- [x] **3.10 Lock the model-input allowlist.** Save explicit feature names separately from identifiers, labels, future-window dates, split/status fields, and provenance. Validate that only allowlisted columns can enter model inputs. **Done when:** tests reject an attempted target, future date, or split field as a feature; SEC columns are absent.
- [x] **3.11 Test the transformations.** Test row/key alignment, shared-session chronology, feature warm-up, incomplete future windows, peer ties and missing peers, training-only risk cutoffs, and no future influence on features. **Done when:** focused tests pass for both ordinary rows and boundary cases.
- [x] **3.12 Save metadata and reproduce the build.** Save formulas, units, class policy, split dates, source and code hashes, output hash, row/class counts, missingness by column, and the run command. Run the command again on the same input. **Done when:** the two datasets and their substantive metadata match; any differing run identifiers or timestamps are documented.

**Completed phase 3 artifact:** `data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv`, with metadata and per-task eligibility flags. Two full builds matched. See `decision.md` for step reviews. Phase 4 evaluation remains pending.

**Preserved intermediate artifact:** `data/processed/model_inputs/market_features_intermediate_2026-10-23T012858Z/market_features.csv` contains market features and nominal split fields. Its missing rolling-window values are intentional; labels begin in step 3.6. Future builds use `market_features_<UTC timestamp>/market_features.csv`.

**Exit evidence:** A saved, reproducible feature/label dataset with metadata and tests for the important transformations.

## Phase 4 — Freeze chronological evaluation

Start with `data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv` and its metadata. The audit found 118,987 eligible rows per task with complete allowlisted features and labels. Keep the original 124,987 rows and their missingness reasons for traceability. The saved `risk_class` uses one development training boundary; recompute risk cutoffs inside every new training fold before scoring.

### Lock the evaluation contract

- [x] **4.1 Verify the phase 3 input.** Check CSV and metadata hashes, unique `(ticker, session_date)` keys, expected class codes, allowlisted features, actual target end dates, and per-task eligibility reasons. **Done when:** one reproducible audit confirms the rows available to each task and fails on corrupted or inconsistent inputs.
- [x] **4.2 Write the bounded experiment protocol.** Name the return and risk tasks, candidate models and simple baselines from phase 5, primary and secondary metrics, feature groups, and a small parameter-search budget. Mark 2024–2025 as reused evidence and specify what would count as a later fresh test before viewing its outcomes. **Done when:** the choices are recorded and versioned before running new comparisons.
- [x] **4.3 Choose chronological development blocks.** Use shared XNYS session dates for all stocks; specify outer training/evaluation date ranges and earlier inner training/validation ranges for each outer block. Do not mix stocks from one date across a fold boundary. **Done when:** every row has at most one role per fold and all training dates precede its evaluation dates.

### Check leakage in every fold

- [x] **4.4 Purge overlapping outcomes.** For each boundary, remove a training row when its actual `target_window_end` is on or after the first evaluation date. Apply the same rule between inner training and validation. **Done when:** saved fold checks show zero training outcome windows reaching an evaluation block, including boundary and missing-end cases.
- [x] **4.5 Apply task-specific row eligibility.** Use `return_eligible` or `risk_eligible`, complete allowlisted features, and present labels for the chosen task. Retain excluded-row counts by date, ticker, and reason. **Done when:** train and evaluation matrices contain no missing required values and the coverage loss is reported.
- [x] **4.6 Refit risk classes inside each fold.** Calculate the 1/3 and 2/3 volatility quantiles from that fold's eligible, purged training outcomes only; apply those fixed cutoffs to its inner validation and outer evaluation rows. Save cutoffs and class counts for each fold. **Done when:** changing later outcomes cannot alter an earlier fold's cutoffs or labels. Treat phase 3's saved risk classes as dataset-version reference labels, not universal fold labels.
- [x] **4.7 Isolate learned preprocessing.** Fit scaling, imputation if later needed, feature selection, and probability calibration on the permitted training portion only. An inner validation used for tuning must not also be used to fit its preprocessing. **Done when:** pipeline checks fail if a fitted transform or calibration step sees evaluation dates.

### Freeze and hand off

- [x] **4.8 Check ranking groups.** For return evaluation, keep each session's eligible peers together and record their counts. Use the approved 45-stock activity and outcome quorum and tie policy; skip a date that lacks enough evaluated peers, with a recorded reason. **Done when:** within-date metrics use only valid groups and no ticker is silently substituted into the reference universe.
- [x] **4.9 Save fold definitions and tests.** Save exact dates, row counts, purged keys/counts, fold-specific risk cutoffs, dataset/code hashes, and tests for chronology, overlap, feature exclusion, missingness and peer groups. **Done when:** a second run reconstructs identical fold membership and metadata from the same inputs.
- [x] **4.10 Freeze the evaluation rule.** State how inner validation selects settings, how later outer folds estimate development performance, and when the reused 2024–2025 period may be reported. Reserve a genuinely later or prospective period for stronger final assessment. **Done when:** phase 5 can compare models without changing folds, metrics, or selection rules after seeing results.

**Exit evidence:** Reproducible fold definitions, leakage tests, a bounded experiment list, and a documented final evaluation rule. Completed in `src/model_training/chronological_evaluation_protocol.py`; the pre-rename report is archived at `reports/generated/archive/pre_refactor_phase4_phase5_2026-10-23/chronological_evaluation_protocol.json`. The full review is in `decision.md`.

## Phase 5 — Compare simple models fairly

Follow the frozen Phase 4 protocol at `reports/generated/current/chronological_evaluation_protocol.json` using the current model-input dataset and its hash. Pre-rename Phase 4–5 evidence is retained under `reports/generated/archive/pre_refactor_phase4_phase5_2026-10-23/`. Save new generated results under `reports/generated/current/`; commit the reproducible code and a concise evaluator-facing report, not large generated tables. Compare models only on matched rows, dates, feature groups and fold-specific labels. Never describe the class rank score as an expected return.

### Establish fair baselines

- [x] **5.1 Verify the frozen inputs.** Check dataset and protocol hashes, fold dates, feature allowlist, task eligibility, and fold-specific risk boundaries before fitting. **Done when:** the run stops on any mismatch and records the exact input versions.
- [x] **5.2 Measure simple baselines.** For return, score the training-class prior and 20-day momentum ordering. For risk, score the training-class prior and trailing volatility converted using that fold's training cutoffs. Keep numerical Ridge and other saved results clearly labeled as prior benchmarks unless rerun on matched phase 4 rows. **Done when:** every candidate will be compared against a baseline on the same eligible observations.
- [x] **5.3 Define matched feature sets.** Compare the four frozen phase 4 groups cumulatively and keep the same feature rows per fold within each comparison. Report coverage separately if a model legitimately needs fewer rows. **Done when:** the feature matrix is selected only from the allowlist and group definitions match the protocol.

### Fit and evaluate return models

- [x] **5.4 Fit the return prior and Logistic Regression.** Train on outer training dates, select any of the three recorded `C` values using that fold's inner validation only, then score the outer block once. Save class probabilities and rank `P(Higher)-P(Lower)`. **Done when:** all four outer folds have predictions and fitting logs identify only permitted training dates.
- [x] **5.5 Fit HistGradientBoosting for return.** Use the recorded three `max_leaf_nodes` values and fixed tree settings; select on inner validation and evaluate on outer dates. Compare same-date Spearman rank correlation with momentum and the training prior. **Done when:** each model has matched out-of-fold predictions and no probability or score is described as a return percentage.
- [x] **5.6 Review return results.** Report fold-level and mean Spearman, macro F1, per-class precision/recall, ordinal error, confusion matrix, and same-date top-10 research diagnostics against momentum. **Done when:** the selected return approach is supported across folds or the benchmark remains selected with the failure recorded.

### Fit and evaluate risk models

- [x] **5.7 Fit the risk prior and Logistic Regression.** Use fold-specific risk classes from phase 4; tune only the recorded `C` values on inner validation. Score macro F1 and probability metrics on the outer block. **Done when:** stored predictions use that fold's fixed cutoffs and no outer outcomes affect training or tuning.
- [x] **5.8 Fit HistGradientBoosting for risk.** Use the recorded tree settings and inner-only selection. Compare with the class prior and trailing-volatility baseline on identical rows. **Done when:** four fold predictions and class-boundary provenance are saved.
- [x] **5.9 Review risk errors.** Report macro F1, per-class precision/recall, confusion matrix, ordinal error, log-loss/Brier score when probabilities are valid, and High outcomes predicted Low. Include numerical volatility MAE/RMSE/R² only as secondary diagnostics. **Done when:** severe risk misses and fold variation are visible beside the average score.

### Prepare evaluator-facing evidence

- [x] **5.10 Produce the evaluator notebook and results package.** Create one presentation notebook that loads the frozen dataset and protocol, calls reusable functions from `src/` for fitting/scoring, and displays the research question, data/fold summary, model comparisons, fold metrics, confusion matrices, limitations, and selected model rationale. Save concise result tables and plots under the ignored `reports/generated/`; include hashes, environment and run instructions. Keep model logic in tested modules instead of copying it into notebook cells. **Done when:** restart-and-run-all reproduces the tables and plots from the recorded inputs, and an evaluator can see fold variation and failure cases beside averages.
- [ ] **5.11 Freeze the Phase 5 conclusion.** Select a candidate only when it improves the predeclared primary metric across folds without unacceptable secondary failures; otherwise retain the simple benchmark. Keep the reused 2024–2025 period out of selection, and state that overlapping 20-session outcomes limit row-wise independence. **Done when:** `decision.md` records evidence, uncertainty and the next step; no claim of an untouched test or trading performance is made.

Random Forest, ordinal models and listwise ranking are later challengers only if the baseline comparison identifies a specific unresolved problem. Any ranker must group by date and its raw score is not a calibrated percentage return.

**Exit evidence:** A reproducible, evaluator-ready report with fold-level return and risk comparisons, baselines, uncertainty and limitations; an evidence-based candidate choice or a documented decision to keep a benchmark. No model is selected from a single fold or reused test period.

## Phase 6 — Improve features in small groups

- Compare existing market factors in groups: momentum, volatility, downside/trend, SPY-relative measures, and volume.
- Consider a limited set of additional trailing measures only when they have a clear definition and point-in-time calculation.
- After SEC validation, test assets/cash and filing-age features. Add debt, revenue growth, profit margin, or historical market capitalization only after their concepts and historical inputs are defensible.
- Compare market-only and market-plus-fundamental models on matched rows; report the coverage lost from missing fundamentals separately.
- Let return and risk models use different feature sets if the evidence supports it.

**Exit evidence:** An ablation report showing the contribution and coverage of each feature group.

## Phase 7 — Tune the strongest candidates within a fixed budget

- Search a small, recorded set of regularization strengths and tree settings on training-side chronological validation only.
- Prevent tree-model early stopping, imputation, scaling, and probability calibration from seeing later evaluation rows.
- For return, prioritize mean within-date rank correlation across folds; report class metrics and matched top-10 selection versus momentum and the same research universe. Ranking metrics and 20-day forward returns are research diagnostics until execution and eligibility rules exist.
- For risk, prioritize macro F1 and inspect High-risk recall, High predicted as Low, probability calibration, and numerical volatility errors.
- Examine results across folds and market periods. Twenty-day future windows overlap, so do not treat daily stock rows as independent evidence of uncertainty.

**Exit evidence:** A documented risk candidate and return candidate, including a reason to retain a simple benchmark if learned alternatives fail to improve reliably.

## Phase 8 — Evaluate on a reserved later period

- Freeze feature definitions, fitted preprocessing strategy, thresholds, hyperparameters, model-selection rules, and all reported metrics before examining new outcomes.
- Train with only historically permitted observations; evaluate once on the reserved later period.
- Report every predeclared metric and failure. Distinguish development folds, the reused 2024–2025 period, and genuinely unseen results.
- If the period is too short or results motivate model changes, record that limitation and require a different future period to evaluate the changed model.

**Exit evidence:** A final research comparison with dataset/code identifiers and limitations. Do not claim an untouched test result from the previously viewed period.

## Phase 9 — Save models and verify inference

- Save the selected fitted preprocessing pipelines and models with feature order, schema, required history, label definitions, training cutoff, class boundaries, data/code versions, dependencies, and evaluation summaries.
- Test that historical inference reproduces the feature calculations used at training and rejects missing, stale, or unavailable inputs clearly.
- Expose stable AI prediction functions through FastAPI when the model and input contract are reviewable. Return categories, probabilities where valid, model version, and explanations; do not present rank scores as expected percentage returns.

**Exit evidence:** Reusable model artifacts and tested inference functions with clear provenance.

## Phase 10 — Evaluate the complete portfolio system

- First document and approve the exact Shariah methodology, historical eligibility rules, portfolio objective, constraints, rebalance schedule, and transaction-cost assumptions. Keep screening separate from ML.
- At each historical rebalance, use only market data and SEC filings available then. Admit only stocks that pass the historical screen. Apply the chosen risk preference through portfolio constraints or weights.
- Use the next tradable session for execution assumptions and compute realized returns from actual entry and exit prices. Account for costs and turnover.
- Compare with an equal-weight compliant portfolio on the same dates and eligible stocks. Report return, volatility, Sharpe ratio, maximum drawdown, turnover, concentration, and holdings.
- Document survivorship bias and other source limitations. Integrate reviewed outputs with the application backend and frontend after the AI service contract is stable.

**Exit evidence:** An explainable research prototype and a reproducible, historically constrained backtest. Model accuracy alone does not establish portfolio usefulness.

## Immediate working order

Phase 1 is approved and phase 2 now supplies a verified-source market input with documented research limitations. Next build the phase 3 saved feature/label dataset using the cleaned path in the phase 2 report. Keep SEC predictors excluded until their separate gate passes. Each later phase begins only when its stated inputs and evaluation rules can be reproduced.
