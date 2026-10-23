# Phase 3 decisions

Earlier history remains in the existing local `decisions.md`. This file records the current contract for Git review.

## 2026-10-23 — Step 3.1 validated input/output contract

- Input: `data/cleaned/20261022T060940848455Z/prices_clean.csv`.
- Recomputed SHA-256: `f5734f6b7e3d2e7e41a877834f1cb5210bcb6845e329543459e49eed84959d21`.
- Source: `data/raw/alpaca/alpaca_sip_20261009T110617242394Z_restored_json_v1`.
- Source manifest hash recorded in phase 2: `7954ead48c0c342fd0b2f8655dd566ac4d65271db12bb6887c356910ccaddaf1`.
- Evidence: `reports/generated/phase2_20261022T060900192314Z/phase2_report.json` and the cleaning directory's `report.json`.
- Saved reports record 127,501 rows including SPY, and 124,987 company rows across 50 companies. These are input counts, not ready-to-train counts or newly rerun validation results.
- Required calculation columns: `ticker`, `session_date`, `open`, `high`, `low`, `close`, `volume`, `adjusted_close`. Unique key: `(ticker, session_date)`.
- Derive `spy_return` from SPY all-adjusted close on a shared XNYS calendar. Use SPY as a benchmark only. Keep company source rows and their provenance/quality fields.
- Step 3.5 output: new `data/modeling/<run_id>/model_dataset.csv`, containing company source columns, `spy_return`, and the 14 features in `src/features/market.py::FEATURE_COLUMNS`. Identify this as a features-only intermediate artifact in metadata. Do not overwrite earlier artifacts.
- Later phase 3 outputs add continuous outcomes, relative-return classes, risk classes, actual target end dates, and split/eligibility fields. Final names and policies must be recorded before implementing labels.
- Use provider all-adjusted close consistently for return features. Features are available after t closes; execution is no earlier than the next observed session. Preserve unresolved flags and missing delivery timestamps. SEC predictors remain excluded.
- Generated CSVs are ignored by Git. Code, tests, documentation and small reproducibility metadata should be reviewable.
- Baseline CSV hash recomputed and unchanged: `ad9b35d6be20564546312259bb75854c4de5c6c3d5a9e5034b7d56e46c9e8a58`.
- Baseline target metadata hash recomputed and unchanged: `30d62e9d7d655efab317e462c890edb5a88a5d557993eb4c61fd51451e59f3f4`.

Review: step 3.1 contract validated against source header, saved reports, and current hashes. No new model dataset has been generated.

## 2026-10-23 — Step 3.2 approved quorum correction

The user replaced the full-universe requirement with a minimum of 45 actively trading reference companies (90% of 50). Count observed valid company bars with positive volume at t as the available-data proxy for active trading; this is not an exchange suspension registry. Record this count independently of future outcome availability. Dates below 45 cannot receive relative-return labels. Preserve their feature rows and independently eligible risk outcomes. The reference universe stays fixed; LIN history is not fabricated.

For later label creation, rank available complete outcomes among the active reference companies using ascending average ranks: Lower if rank <= n/3, Middle if rank <= 2*n/3, Higher otherwise, where n is the outcome peer count. Equal returns receive the same class; ties can produce uneven groups. Require at least 45 complete outcomes as well as the activity quorum, and record both counts. A missing outcome never becomes a zero return. This conservative outcome guard retains ordinary 49-company dates while avoiding labels based on a tiny surviving subset. No labels are calculated in steps 3.1–3.5.

Review: 44 active companies fail, 45 and 49 pass; the denominator for ranking is the actual eligible peer count. The user's correction supersedes the earlier full-50 proposal and qualifies the original fixed-universe specification.

## Step 3.3 — Development split and label contract

Preserve the saved benchmark's development boundaries for comparability: training dates before 2022-12-28, validation before 2024-07-01, and reused test dates from 2024-07-01. This is not a fresh holdout. Future label windows use the shared XNYS calendar, not each ticker's observed-row count. Purge training windows ending on or after validation start, and validation windows ending on or after test start. In step 3.5 these are nominal split fields only; training eligibility awaits outcome completeness and purging in later steps.

Return codes are 0/1/2 = Lower/Middle/Higher. Risk codes are 0/1/2 = Low/Medium/High. Risk boundaries are pooled eligible, unpurged training-outcome quantiles at 1/3 and 2/3, with lower intervals inclusive at their upper boundary. Risk is sample standard deviation of adjusted daily returns t+1 through t+20 times sqrt(252). Return is adjusted close(t+20)/adjusted close(t)-1. Preserve the after-close prediction convention; execution starts no earlier than the next session. Phase 4 must fit risk boundaries anew within each training fold. No cutoffs are estimated in the features-only build.

Review: chronological boundaries match preserved metadata; the reused test limitation and actual-end-date purge requirement are explicit. Proceed to the build and feature calculations.

## Steps 3.4 and 3.5 — Build and feature validation

Command: `.\.venv\Scripts\python.exe -m src.features.build_dataset`.

Saved output: `data/modeling/20261023T012858924857Z/model_dataset.csv`, with `features_metadata.json` beside it. The build produced 124,987 company rows, 14 market features, and 121,987 rows with all 14 features present. There are 713 sessions with 49 active companies and 1,801 with 50. All pass the activity quorum; future outcome eligibility is still pending.

Step 3.4 review: focused tests pass for invalid inputs, missing SPY sessions, checksum mismatch, output overwrite rejection, and 44/45/49-company quorum boundaries. Step 3.5 review: tests pass for alignment, warm-up missingness, missing bars, and invariance of earlier features when future prices change. Six unittest tests passed across `test_feature_dataset.py` and `test_market_features.py`. Pytest is not installed in the existing environment, so the tests used their standard-library unittest runner. The environment reports Python 3.14.8; these checks do not establish full dependency compatibility or replace the project's recommended 3.11/3.12 environment.

The original model CSV and target metadata still match the hashes recorded in step 3.1. New generated CSV data remains ignored by Git; code, tests and small metadata can be committed. No model training or new outcome labels were run. Steps 3.6 onward remain pending.

## 2026-10-23 — Feature review and artifact naming

The features-only output is now `data/modeling/market_features_20261023T012858924857Z/market_features.csv`. Future builds use `data/modeling/market_features_<UTC timestamp>/market_features.csv`. The timestamp distinguishes reproducible runs while the names state their contents. The renamed CSV's SHA-256 remains `f693cfd611d85898e25f88614d38834121d6f1630a37eb5323c24490aca24570`.

The 20- and 60-session volatility features measure standard deviation of all daily returns, whether positive or negative. `downside_dev_20d` is an additional predictor that measures negative daily returns relative to zero; it does not define the risk target. Future risk labels remain symmetric 20-session realized volatility. Whether this predictor improves a risk model is an empirical Phase 6 comparison, not an assumed gain.

The 124,987-row audit found no duplicate ticker/date keys and no zero-volume company bars. Missing feature values match rolling warm-up: 50 first-day returns, 1,000 20-return volatility values, and 3,000 60-return volatility values. Price-to-average windows need one fewer earlier return. Source fields `dividend_per_share`, `split_ratio`, and `bar_available_at` are blank in all rows; they remain source provenance limitations. The 49 missing SPY returns are the first benchmark date repeated across 49 listed companies. No missing source field is imputed into a model feature.

## 2026-10-23 — Steps 3.6–3.12 completed

Command: `.\.venv\Scripts\python.exe -m src.labels.phase3 --output-dir data/modeling/market_features_and_labels_phase3_v1` (use a new output directory to repeat).

Output: `data/modeling/market_features_and_labels_phase3_v1/market_features_and_labels.csv` and `dataset_metadata.json`. The command reproduces the build in a temporary directory and compares complete metadata and CSV hashes. Both matched. Original snapshots retained their recorded hashes.

- 3.6 review: independent numerical test confirms close-to-close return and sample volatility over t+1 through t+20, with all final 20 sessions unlabeled and gaps invalidating the window.
- 3.7 review: 44-company groups fail; 45, 49 and 50 pass. Average ranks preserve ties; all-equal groups become Middle. A 45-company group missing one outcome fails the outcome quorum.
- 3.8 review: cutoffs use 83,237 complete-feature, unpurged training rows. Annualized decimal volatility cutoffs are 0.1821350131728024 and 0.28472429127576987. Changing later outcomes leaves these boundaries and earlier classes unchanged. Phase 4 must refit boundaries inside each fold.
- 3.9 review: original columns and row order are asserted equal during every build. Actual end dates purge 2,000 rows. Separate task eligibility fields explain purging, missing features, or missing labels; return_label_reason explains missing peer labels.
- 3.10 review: model_inputs selects only the 14 market features and rejects non-allowlisted inputs. Targets, future dates, eligibility fields, splits and provenance cannot be selected through this function.
- 3.11 review: three new phase 3 tests and six existing feature tests passed. Saved CSV checks cover keys, boundary isolation, complete eligible model inputs and terminal missing outcomes.
- 3.12 review: two full builds produced identical CSV hashes and substantive metadata. The table has 124,987 rows and 118,987 eligible rows for each task. Metadata records class counts across all labeled rows, including rows excluded from fitting; select task eligibility before modeling.

An initial metadata serialization failure was corrected by converting class-count keys to strings and validating JSON before writing. The incomplete new output was removed before rerunning; earlier work was preserved. Generated CSV remains Git-ignored. No model fitting was performed, and the reused test period remains reused evidence. The environment remains Python 3.14.8 with focused checks only, rather than a claim of full supported-version compatibility.

## 2026-10-23 — Final phase 3 dataset review before phase 4

Re-read the saved phase 3 CSV and metadata. The CSV SHA-256 matches metadata, all 124,987 ticker/date keys are unique, and each task has 118,987 eligible rows with zero missing allowlisted feature cells and zero missing task labels. Each task excludes 6,000 rows in total under the recorded warm-up, missing-future, and purge rules. There are 3,000 rows with at least one missing market feature, intentionally retained for audit and excluded through eligibility. `bar_available_at`, `dividend_per_share`, and `split_ratio` remain blank across the source rows and are excluded from model inputs.

Decision: the dataset is ready as a cleaned, feature-engineered, labeled **research input** for phase 4 evaluation design. It is not a universally complete CSV; downstream code must filter by task eligibility and the explicit feature allowlist. Phase 4 must also derive risk class boundaries within each fold and check actual outcome-window overlap. Expanded the Phase 4 roadmap into ten checkable steps in `docs/Phases.md`; no model evaluation was run during this review.

## 2026-10-23 — Phase 4 evaluation protocol frozen

Command: `.\.venv\Scripts\python.exe -m src.modeling.evaluation_protocol --output reports/generated/phase4_protocol_final.json`. The JSON is a generated local report; `src/modeling/evaluation_protocol.py`, tests, this decision, and `docs/Phases.md` are the Git-reviewable source. A second in-memory run produced an identical report. Four outer folds use 252 shared XNYS sessions each; each has a 126-session earlier inner validation block. Outer evaluation windows begin 2020-06-26, 2021-06-28, 2022-06-28, and 2023-06-29. The inspected 2024-07 onward period is excluded from development.

Step reviews:

1. **4.1** The audit checks the saved data hash, row count, unique keys, fixed 20-session actual target ends, class codes, feature allowlist, and eligible-row completeness. A deliberately corrupted copy fails. The input remains 124,987 rows with 118,987 eligible per task.
2. **4.2** The report freezes tasks, baselines, metrics, four existing feature groups, Logistic Regression and HistGradientBoostingClassifier candidates, and a three-value grid per model. Rank score is `P(Higher)-P(Lower)`; it is not a forecast percentage return. A verified period after 2025-12-31 counts as fresh only if settings are frozen before its outcomes are viewed.
3. **4.3** Shared dates keep stocks from one session together. All train dates precede their fold's evaluation dates. Four outer and four earlier inner date ranges are saved.
4. **4.4** Each training row's actual `target_window_end` must precede the first evaluation date. Inner evaluation outcomes must also end before the outer evaluation starts. All 16 task/role boundaries pass; purged key lists and counts are saved.
5. **4.5** Each task uses its own eligibility flag, nonmissing label and all 14 allowlisted features. Exclusions are recorded by reason, ticker and date, with row counts and key hashes for each role.
6. **4.6** Inner and outer risk boundaries are separately fitted on their eligible training outcomes. Frozen boundaries are applied to evaluation outcomes, with class counts saved. Phase 3's global development risk class is not reused as a fold label.
7. **4.7** A guarded fitting path accepts only allowlisted training features and rejects evaluation overlap; a separate guard reserves earlier, nonoverlapping rows for calibration. Preprocessing and calibration fitting remain Phase 5 work.
8. **4.8** Return evaluation groups contain 45–50 eligible reference stocks; group sizes and counts are saved. Invalid or missing peer groups cause protocol generation to fail.
9. **4.9** The report records exact date bounds, role row counts, purged keys, key hashes, risk cutoffs, input and code hashes. A second run matched it exactly. Three focused tests pass, including tamper rejection, overlap failure and fixed-boundary behavior.
10. **4.10** Inner validation alone selects settings; later outer folds estimate development performance. The 2024–2025 period remains reused evidence. The prospective test rule is recorded before Phase 5 fitting.

The initial fold run showed that a planned evaluation start may have no eligible row because of an earlier purge. The chronology guard now accepts the first eligible date within the planned block while still enforcing that training outcomes end before the planned boundary. No model was trained and no performance metric was produced in Phase 4.

## 2026-10-23 — Phase 5 work plan

Expanded Phase 5 into 11 small steps: verify frozen inputs; establish matched baselines; define feature sets; fit and review return models; fit and review risk models; produce the evaluator report; and freeze the conclusion. The plan uses Phase 4's fixed folds and limited search grids. It requires fold-level results, confusion matrices, risk-underestimation review, matched momentum comparisons, reproducibility identifiers, and limitations. It keeps model choice in development folds and excludes the reused 2024–2025 evidence from selection. No model was trained as part of this planning change; Phase 5 exit evidence must be produced from actual runs.

## 2026-10-23 — Phase 5 dataset and presentation format

Phase 5's primary input is `data/modeling/market_features_and_labels_phase3_v1/market_features_and_labels.csv` (124,987 rows; phase 3 metadata SHA-256 `71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f`). The frozen evaluation plan is `reports/generated/phase4_protocol_final.json`, which binds folds to that dataset hash. Model code must filter task eligibility and use fold-specific risk boundaries from the protocol.

Decision: use a Jupyter notebook as the evaluator-facing narrative and visual presentation. Keep the training/evaluation implementation in reusable, tested `src/` modules and have notebook cells call that code. This makes the notebook presentable while keeping results reproducible and reviewable. No notebook or model experiment was created in this decision update.

## 2026-10-23 — Phase 5 steps 5.1 and 5.2 validated

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_baselines --output reports/generated/phase5_baselines.json` from the repository root. The generated report is local and Git-ignored; the reproducible source is `src/modeling/phase5_baselines.py` with `tests/test_phase5_baselines.py`. On a second run, choose a new output path because the command refuses to overwrite an existing report. If the Phase 4 report is absent in another checkout, regenerate it first with `.\.venv\Scripts\python.exe -m src.modeling.evaluation_protocol --output reports/generated/phase4_protocol_final.json`.

**5.1 review.** The runner checks the exact Phase 3 CSV SHA-256 `71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f` and Phase 4 protocol SHA-256 `0ce0a17f2595b253331f8d8ab548365d346e9488af83f650a515aa92ef9b60e5`, then rebuilds the complete protocol from the audited data and requires equality. This rechecks all four fold dates, row-key hashes, purges, task eligibility, feature allowlist, peer groups, and inner/outer training-derived risk cutoffs. A deliberately changed protocol is rejected. No model fitting occurs.

**5.2 review.** Sixteen baseline results were produced: return and risk for both inner and outer roles of each of four folds. Every result records the same evaluation key hash and row count as its frozen Phase 4 role. Training-class priors use only that role's training labels; the risk labels and trailing-volatility categories use that role's frozen cutoffs. The prior's most frequent class uses the lowest code on a tie. A constant return prior cannot order stocks, so its Spearman and top-10 result are explicitly undefined. Momentum orders the same 45–50 eligible stocks per date. The prior has classification, log-loss, and multiclass Brier results; these are matched baselines for later models. The table below shows outer roles only.

| Outer fold | Return prior macro F1 | Momentum mean daily Spearman | Risk prior macro F1 | Trailing-volatility macro F1 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0.1692 | -0.0331 | 0.0820 | 0.5111 |
| 2 | 0.1692 | 0.0144 | 0.0975 | 0.5484 |
| 3 | 0.1692 | -0.0122 | 0.0969 | 0.5647 |
| 4 | 0.1692 | 0.0332 | 0.1882 | 0.5062 |

The mean of four momentum fold means is 0.0006; the mean trailing-volatility macro F1 is 0.5326. These are development baselines, not model-selection or trading results. The momentum top-10 forward-close diagnostics in the generated report use a close already known at signal time and are not executable returns. Previously saved Ridge and SPY-relative results use another dataset/task and have not been rerun on matched Phase 4 rows. Three focused tests pass, including protocol tamper rejection, exact fold-row matching, fixed risk cutoffs, and no arbitrary rank score for a constant prior. Steps 5.3 onward remain pending.

## 2026-10-23 — Step 5.3 matched feature sets

`matched_feature_sets` in `src/modeling/phase5_baselines.py` reads the four ordered groups directly from the frozen Phase 4 protocol, checks every column against its allowlist, and uses the guarded fold feature selector. The cumulative sets have 4, 9, 12, and 13 columns. `momentum_5d` is allowlisted in the dataset but absent from the frozen groups, so it is excluded from this comparison rather than silently added. Changing the group order, repeating a feature, using a forbidden column, or encountering a missing selected value fails clearly.

Review: all 16 inner/outer task roles produced all four matrices, for 64 matched sets. Within each role, all four sets retain the exact same training and evaluation row counts. For example, fold 1 outer return has 51,687 training and 12,600 evaluation rows at every feature level. No model was fitted and no new score was claimed. Later models should call this selector and compare against the step 5.2 baselines using the role's frozen evaluation keys. Step 5.4 is next.

## 2026-10-23 — Step 5.4 return prior and Logistic Regression

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_return_logistic --output-dir reports/generated/phase5_return_logistic` on a checkout without that output directory; use a new output directory for a repeated run. Source: `src/modeling/phase5_return_logistic.py`. Generated `report.json` and `outer_predictions.csv` are Git-ignored. The report records dataset SHA-256 `71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f`, Phase 4 protocol SHA-256 `0ce0a17f2595b253331f8d8ab548365d346e9488af83f650a515aa92ef9b60e5`, code hashes, environment, candidates, dates, row-key hashes, selected settings, and prediction hash.

Only `relative_return_class` (0/1/2 = Lower/Middle/Higher) enters fitting as the target. Each feature matrix uses one of the four cumulative frozen groups, selected through the allowlist guard; the model helper independently rejects targets and identifiers as inputs. StandardScaler and Logistic Regression are fitted together on inner training rows for each of the frozen `C` values 0.1, 1, 10. The selection metric is mean same-date Spearman between `P(Higher)-P(Lower)` and realized continuous return on inner validation. Ties keep the protocol's group and C order. The selected setup is refitted on outer training rows; outer outcomes are used only for scoring. No probability calibration or other tuning uses outer rows. The saved prior probabilities and class derive from outer training class counts.

Review: training targets end before each validation start; inner validation targets end before each outer evaluation start. All four fitted training-role key hashes match the frozen protocol. The output has 48,400 outer predictions with unique fold/ticker/date keys, all before 2024-07-01. The three class probabilities sum to one within numerical precision, and the saved rank score equals `p_higher-p_lower`. A focused test confirms probability order, training-only scaling, and target-column rejection.

| Fold | Selected group | C | Inner mean Spearman | Outer model Spearman | Outer momentum Spearman | Outer model macro F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | trend_downside | 0.1 | 0.0648 | 0.1020 | -0.0331 | 0.3350 |
| 2 | market_relative | 0.1 | 0.1439 | -0.0322 | 0.0144 | 0.2936 |
| 3 | trend_downside | 0.1 | -0.0551 | 0.1311 | -0.0122 | 0.3681 |
| 4 | trend_downside | 10.0 | 0.2123 | -0.0476 | 0.0332 | 0.3151 |

The model's mean outer Spearman is 0.0383 versus 0.0006 for matched momentum, but it wins only two folds. This is mixed development evidence, not a final return-model choice. The score is an ordering signal, not a percentage return; selected-stock forward-close outcomes are research diagnostics. Step 5.5 and the fuller 5.6 review remain pending.

## 2026-10-23 — Step 5.5 return HistGradientBoosting

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_return_histgbm --output-dir reports/generated/phase5_return_histgbm` using a new output directory on repetition. The code reads the same frozen Phase 3 dataset and Phase 4 protocol as step 5.4. It uses only `relative_return_class` as the training target and cumulative allowlisted market feature sets as inputs. The model helper independently rejects a target or identifier column in the feature matrix. The frozen tree grid is `max_leaf_nodes` 15, 31, 63, with `max_iter=100`, `learning_rate=0.1`, `early_stopping=False`, and `random_state=42`. No internal random validation split is used.

Each fold selects its group and leaf setting by inner-validation mean within-date Spearman of `P(Higher)-P(Lower)` versus observed continuous return. It then refits on outer training rows and scores the outer block once. Training outcome windows end before the relevant validation/evaluation boundary, and training row-key hashes match the frozen protocol. The generated report includes candidate metrics, selected settings, fit dates, input/code versions and prediction hash. Saved outer predictions have the same 48,400 fold/ticker/date keys in the same order as Logistic Regression, valid three-class probabilities, and no reused-test rows. The training-class prior is constant within a fold, so its Spearman is undefined rather than an artificial zero. The focused input-guard test passed.

| Fold | Selected group | Leaves | Tree Spearman | Momentum Spearman | Logistic Spearman |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | trend_downside | 15 | 0.0481 | -0.0331 | 0.1020 |
| 2 | momentum_volatility | 15 | 0.0068 | 0.0144 | -0.0322 |
| 3 | momentum_volatility | 15 | -0.0309 | -0.0122 | 0.1311 |
| 4 | market_relative | 15 | -0.0212 | 0.0332 | -0.0476 |

Mean outer same-date Spearman is 0.0007 for the tree, 0.0006 for momentum, and 0.0383 for Logistic Regression. These are matched development folds, but fold-level differences are mixed. The 5.6 review must examine class errors and research top-10 diagnostics before any return approach is selected. The rank score is not a forecast percentage return.

## 2026-10-23 — Step 5.6 matched return review

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_return_review --output reports/generated/phase5_return_review.json` with a fresh output path on repetition. The review reads the frozen protocol and saved Logistic Regression and HistGradientBoosting predictions; it checks their code and prediction hashes, identical targets/baselines, exact matched fold/ticker/date keys, and the frozen evaluation-key hashes. No model is refitted or tuned. `src/modeling/phase5_return_review.py` is Git-reviewable; the full generated report is ignored. It contains four fold-level confusion matrices, per-class precision/recall/F1/support, macro F1, ordinal error, daily ranking and top-10 diagnostics, paired differences, and source hashes.

| Outer fold | Momentum Spearman | Logistic Spearman | Tree Spearman | Momentum top-10 spread | Logistic top-10 spread | Tree top-10 spread |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.0331 | 0.1020 | 0.0481 | 0.21% | 1.42% | 0.97% |
| 2 | 0.0144 | -0.0322 | 0.0068 | 0.23% | -0.24% | -0.08% |
| 3 | -0.0122 | 0.1311 | -0.0309 | 0.62% | 2.29% | -0.02% |
| 4 | 0.0332 | -0.0476 | -0.0212 | 1.10% | -0.10% | -0.11% |

Equal-weight mean fold Spearman: momentum 0.0006, Logistic Regression 0.0383, tree 0.0007. Mean fold top-10 minus universe spread: momentum 0.54%, Logistic Regression 0.84%, tree 0.19%. Logistic Regression beats momentum on rank correlation in 2/4 folds; the tree does so in 1/4. Across 968 densely overlapping daily selection dates, Logistic Regression's top-10 spread exceeds momentum on 466 dates and the tree's on 431 dates. These date counts are descriptive, not independent trials.

Mean fold macro F1 is 0.1692 for the training-class prior, 0.3280 for Logistic Regression, and 0.3490 for the tree. The generated report gives the complete class-level error evidence; these class gains do not override inconsistent ranking, which is the return task's primary stock-selection metric. The prior has no within-date ordering, so rank correlation and top-10 selection are undefined for it.

Decision for the current development comparison: select no return approach. Keep trailing 20-day momentum only as a simple benchmark/control; it is not an ML model or an endorsed effective strategy. Its mean outer Spearman of 0.0006 is effectively zero, so it showed almost no average monotonic relationship with the next 20-session relative returns. Logistic Regression had a higher mean (0.0383) but was positive in only two folds; HistGradientBoosting averaged 0.0007 and was positive in one fold. Neither learned model meets the consistency rule. The 0.54% mean top-10 momentum spread is a separate descriptive result across four periods and does not establish reliable ranking or executable performance. No Shariah screen, next-session entry price, trading costs, or survivorship correction is applied; top-10 forward-close spreads are research diagnostics rather than portfolio returns. The reused 2024–2025 period remains excluded. Step 5.7 begins the separate risk-model task.

## 2026-10-23 — Step 5.7 risk prior and Logistic Regression

Command: `.\.venv\Scripts\python.exe -m src.modeling.phase5_risk_logistic --output-dir reports/generated/phase5_risk_logistic`; choose a fresh output directory to repeat. Source is `src/modeling/phase5_risk_logistic.py`; generated predictions and report remain Git-ignored. The report records dataset/protocol/helper code hashes, environment, exact frozen role keys, inner and outer cutoffs, candidate settings, metrics, and prediction hash.

Risk classes are recomputed from `risk_volatility_next_20d` using the Phase 4 *inner training* cutoffs for inner tuning, then the distinct *outer training* cutoffs for final fold fitting/scoring. The saved Phase 3 global `risk_class` is never used as a target. All four inner and outer class-count vectors match the frozen protocol. `relative_return_class`, future risk values, dates, and other provenance fields cannot enter the guarded feature matrices; only the cumulative allowlisted market feature groups enter StandardScaler and Logistic Regression. The three frozen C values (0.1, 1, 10) are compared by inner macro F1. Scaling is fitted on inner or outer training rows only. Outer outcomes do not choose settings or cutoffs.

| Outer fold | Selected group | C | Risk model macro F1 | Training-prior macro F1 | Model log loss |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | volume | 0.1 | 0.5088 | 0.0820 | 0.8758 |
| 2 | momentum_volatility | 0.1 | 0.5648 | 0.0975 | 0.8517 |
| 3 | momentum_volatility | 0.1 | 0.6133 | 0.0969 | 0.7891 |
| 4 | volume | 1.0 | 0.5775 | 0.1882 | 0.8548 |

Review: 48,400 saved outer rows have unique fold/ticker/date keys, valid three-class probabilities, no reused-test dates, and the recorded prediction checksum. The fitted training outcome windows end before their corresponding validation/evaluation starts; training key hashes match the protocol. Mean fold macro F1 is 0.5661 for Logistic Regression versus 0.1161 for the training-class prior. Mean log loss is 0.8428 versus 1.0986; mean summed multiclass Brier is 0.5123 versus 0.6667. These are development results and do not establish a final risk model. Step 5.8 will compare HistGradientBoosting on the same risk cohort, followed by the fuller error review in 5.9.

## 2026-10-23 — Step 5.8 risk HistGradientBoosting

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_risk_histgbm --output-dir reports/generated/phase5_risk_histgbm` from the repository root. A repeated run needs a new output directory because the command refuses to overwrite an existing artifact. The implementation is `src/modeling/phase5_risk_histgbm.py`; its generated `report.json` and `outer_predictions.csv` stay Git-ignored. The report records input, protocol, code and matched Logistic Regression prediction hashes, candidate settings, fit dates, fold key hashes, cutoffs, probability metrics, and class counts through the frozen Phase 4 contract.

Inner risk classes use only the inner training volatility cutoffs; outer fitting and scoring use the distinct outer training cutoffs. The Phase 3 global `risk_class` is not used. Twelve candidates per fold combine the four frozen cumulative feature groups with `max_leaf_nodes` 15, 31 and 63. Fixed settings are `max_iter=100`, `learning_rate=0.1`, `early_stopping=False`, and `random_state=42`. Inner macro F1 alone selects the group and leaf count; the selected tree is refitted on outer training rows. The fitting helper accepts only allowlisted market features and explicit fold risk labels. No internal early-stopping validation or outer labels enter fitting or tuning.

| Outer fold | Selected group | Leaves | Tree macro F1 | Logistic macro F1 | Trailing-volatility macro F1 | Prior macro F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | trend_downside | 63 | 0.5129 | 0.5088 | 0.5111 | 0.0820 |
| 2 | market_relative | 15 | 0.5587 | 0.5648 | 0.5484 | 0.0975 |
| 3 | momentum_volatility | 15 | 0.6125 | 0.6133 | 0.5647 | 0.0969 |
| 4 | volume | 15 | 0.5881 | 0.5775 | 0.5062 | 0.1882 |

Review: the output has 48,400 unique outer fold/ticker/date keys and exactly matches the earlier risk Logistic Regression cohort, fold classes and training-prior values. For every fold, the output key hash equals the frozen Phase 4 evaluation hash, recomputed classes match the saved outer cutoffs, and the fitted training outcome windows end before evaluation starts. All three model probabilities are finite and sum to one; no reused-test dates appear. The saved prediction SHA-256 is `1533487fec8450c95e43afbf52807472f4f7362f84161f8a84c7c0e8fd1c3da3`.

Equal-weight mean fold macro F1 is 0.5681 for the tree, 0.5661 for Logistic Regression, 0.5326 for trailing volatility, and 0.1161 for the prior. Mean tree log loss is 0.8411 versus 0.8428 for Logistic Regression. The small average tree advantage changes direction across folds: each learned model leads in two. Step 5.9 must inspect High-risk recall, severe underestimation, class confusion and probability quality before selecting a risk approach. These remain development results, not a fresh test or trading-performance claim.

## 2026-10-23 — Step 5.9 matched risk error review

Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_risk_review --output reports/generated/phase5_risk_review.json` from the repository root, choosing a fresh output path to repeat. The Git-reviewable source is `src/modeling/phase5_risk_review.py`; the full generated JSON stays ignored. The reviewer fits no models. It verifies the frozen protocol checksum, saved model and helper code hashes, prediction hashes, identical fold/ticker/date/target/prior rows, exact Phase 4 evaluation-key hashes, fold risk cutoffs, recomputed classes, and training-class priors before calculating metrics. A focused class-order and severe-miss test passes.

| Matched outer-fold method | Mean macro F1 | Mean High recall | High predicted Low / 20,502 High outcomes | Mean ordinal MAE | Mean log loss | Mean multiclass Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.5661 | 0.6339 | 1,704 (8.31%) | 0.4597 | 0.8428 | 0.5123 |
| HistGradientBoosting | 0.5681 | 0.6333 | 1,109 (5.41%) | 0.4468 | 0.8411 | 0.5098 |
| Trailing volatility class baseline | 0.5326 | 0.6569 | 1,084 (5.29%) | 0.4837 | — | — |
| Training-class prior | 0.1161 | 0.0000 | 20,502 (100%) | 1.2016 | 1.0986 | 0.6667 |

The prior predicts Low in these folds because the training class counts are nearly equal and the frozen tie rule chooses code 0; it is a weak reference, not a risk-management proposal. The trailing baseline has no class probabilities, so log loss/Brier are not invented for it. Its direct numerical annualized-volatility forecast has equal-weight mean fold MAE 0.0875, RMSE 0.1260, and R² 0.0983; these are secondary continuous-target diagnostics and are not classifier outputs. The JSON includes all four per-fold confusion matrices, per-class precision/recall/F1/support, severe-miss rates, probability scores, and the trailing numerical errors.

Review: the tree's macro F1 exceeds trailing volatility in all four folds, but its gain over Logistic Regression is only 0.0020 on the mean and reverses direction across folds. The tree has fewer severe High-to-Low misses than Logistic Regression and slightly better ordinal error, log loss and Brier. Trailing volatility has slightly higher High recall and 25 fewer severe misses than the tree across all rows. Keep the tree as a provisional risk candidate for the Phase 5 conclusion; do not claim a final selection until step 5.11 weighs these tradeoffs and limitations. Overlapping 20-session outcomes reduce row-wise independence, and the reused test period remains excluded.

## 2026-10-23 — Step 5.10 evaluator notebook and results package

Created `notebooks/Phase5_Evaluator.ipynb` and `src/modeling/phase5_evaluator.py`. Run `.\.venv\Scripts\python.exe -m src.modeling.phase5_evaluator` from the repository root to generate the tables and figures without a notebook UI. In Jupyter, open the notebook and use Restart & Run All. It locates the repository root, verifies the frozen Phase 3 dataset and Phase 4 protocol, invokes the reusable `src/modeling` fitting runners if a model artifact is absent, reviews the matched saved predictions, and presents the research question, fold design, return/risk results, class errors, all four folds' confusion matrices, provenance, decisions, and limits. Existing complete model artifacts are reused; the source reviewers check their prediction and code hashes before presentation. Incomplete artifacts fail rather than being silently replaced.

Generated local package: `reports/generated/phase5_evaluator/summary.json`, five concise CSV tables, and two SVG figures. The package is ignored by Git; notebook, orchestrator, and decisions are reviewable source. The summary records the exact dataset/protocol/model-prediction, notebook, orchestrator and artifact hashes, library versions, row counts and limitations. It states that no return approach is selected and the tree is only a provisional risk candidate pending step 5.11.

Review: the package contains 4 fold rows, 16 return metric rows, 16 risk metric rows, 48 per-class rows, and 144 confusion-matrix cells. Both SVG files parse as valid XML. A fresh Python process executed all six notebook code cells in order; the second run reproduced all seven table/figure SHA-256 hashes. `git diff --check` passed. The local `.venv` has Python 3.14.8 and lacks a Jupyter kernel and plotting library, so this check exercised the notebook's Python cells and SVG files rather than the Jupyter UI. An evaluator needs a Jupyter-capable kernel to view the notebook interactively. The source and existing requirements are not expanded merely for notebook rendering. The project documentation recommends Python 3.11/3.12; this local execution does not establish compatibility across supported versions.
