# Pre-9.2 distribution and leakage audit v1

**Audit date:** 2026-11-27  
**Scope:** frozen Phase 6/7 market dataset, chronological protocol, Phase 7
candidate runner, and recorded Phase 7 evidence  
**Execution:** read-only review; no model was trained, tuned, or evaluated

## Verdict

The recorded Phase 7 experiment has strong controls against **direct** leakage:
chronological nested folds, a 20-session target-window purge, training-only
risk boundaries, training-only scaling, inner-validation-only hyperparameter
selection, an allowlisted feature set, and exclusion of the previously viewed
2024-2025 period from development selection.

This does not prove that the selected AI models will generalize. Both were
chosen after repeated research on the same four development folds, and neither
has an untouched final evaluation. The 2026 reserved result belongs to the
simple benchmark procedures, not to the selected Logistic Regression and
HistGradientBoosting candidates.

**Gate decision:** Phase 9.2 may define a contract only if it also freezes a
training-only final-fit rule and labels the resulting artifacts as
development-evidence models. Packaging must not claim untouched-test support.
If an untouched claim is required, a genuinely later, previously unseen period
must be reserved before its outcomes are inspected.

## Dataset coverage

The validated Phase 7 handoff records:

| Item | Recorded value |
| --- | ---: |
| Dataset rows | 124,987 |
| Companies | 50 |
| Market sessions | 2,514 |
| Return-eligible rows | 118,987 |
| Risk-eligible rows | 118,987 |
| Eligible share | 95.20% |
| Previously viewed period excluded from development folds | Starts 2024-07-01 |

The fixed 50-company universe creates survivorship and selection bias. Equal
row counts also do not mean independent observations: company returns share
market shocks, and adjacent 20-session targets overlap.

## Chronological fold distribution

Each fold uses an expanding outer training window. A 126-session inner block
selects hyperparameters, then the chosen setting is refit on the outer training
rows and scored once on the following outer block.

| Fold | Inner training dates (rows) | Inner validation dates (rows) | Outer training dates (rows) | Outer evaluation dates (rows) |
| --- | --- | --- | --- | --- |
| 1 | 2016-03-31 to 2019-11-25 (45,387) | 2019-12-26 to 2020-05-28 (5,300) | 2016-03-31 to 2020-05-28 (51,687) | 2020-06-26 to 2021-06-25 (12,600) |
| 2 | 2016-03-31 to 2020-11-24 (57,987) | 2020-12-24 to 2021-05-27 (5,300) | 2016-03-31 to 2021-05-27 (64,287) | 2021-06-28 to 2022-06-27 (12,600) |
| 3 | 2016-03-31 to 2021-11-24 (70,587) | 2021-12-27 to 2022-05-26 (5,300) | 2016-03-31 to 2022-05-26 (76,887) | 2022-06-28 to 2023-06-28 (11,600) |
| 4 | 2016-03-31 to 2022-11-25 (83,187) | 2022-12-28 to 2023-05-30 (5,250) | 2016-03-31 to 2023-05-30 (88,487) | 2023-06-29 to 2024-05-30 (11,600) |

“Outer evaluation” is the correct description. These four blocks are
development tests, not four independent final tests, because their results
influenced later project choices.

## Return-label distribution

Return labels are cross-sectional on each date: Lower, Middle, and Higher are
assigned from that date's eligible future-return ranks. They are not global
thresholds learned from future dates. Every recorded validation/evaluation
group contains all 50 companies.

| Fold and role | Dates | Lower | Middle | Higher | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 inner validation | 106 | 1,696 | 1,802 | 1,802 | 5,300 |
| 1 outer evaluation | 252 | 4,032 | 4,284 | 4,284 | 12,600 |
| 2 inner validation | 106 | 1,696 | 1,802 | 1,802 | 5,300 |
| 2 outer evaluation | 252 | 4,032 | 4,284 | 4,284 | 12,600 |
| 3 inner validation | 106 | 1,696 | 1,802 | 1,802 | 5,300 |
| 3 outer evaluation | 232 | 3,712 | 3,944 | 3,944 | 11,600 |
| 4 inner validation | 105 | 1,680 | 1,785 | 1,785 | 5,250 |
| 4 outer evaluation | 232 | 3,712 | 3,944 | 3,944 | 11,600 |

The small Lower-class difference is the deterministic consequence of splitting
50 ranks into thirds (16 Lower, 17 Middle, 17 Higher), not missing labels.
Training labels use the same same-date rule. The protocol records training row
counts and validates all labels, but does not serialize per-class return counts
for every training role. Phase 9 final-fit validation should add that summary
before fitting rather than assuming balance from total rows.

## Risk-label distribution

Risk cutoffs are recalculated from each role's training outcomes only. This
makes training classes approximately equal by construction while allowing the
later distribution to shift honestly.

| Fold/role | Training Low/Medium/High | Later Low/Medium/High | Training-only cutoffs |
| --- | --- | --- | --- |
| 1 inner | 15,129 / 15,129 / 15,129 | 255 / 654 / 4,391 | 0.15639, 0.23604 |
| 1 outer | 17,229 / 17,229 / 17,229 | 1,766 / 4,807 / 6,027 | 0.16112, 0.25326 |
| 2 inner | 19,329 / 19,329 / 19,329 | 845 / 2,306 / 2,149 | 0.16744, 0.26433 |
| 2 outer | 21,429 / 21,429 / 21,429 | 2,159 / 3,864 / 6,577 | 0.17142, 0.26693 |
| 3 inner | 23,529 / 23,529 / 23,529 | 277 / 1,106 / 3,917 | 0.17137, 0.26527 |
| 3 outer | 25,629 / 25,629 / 25,629 | 1,972 / 4,384 / 5,244 | 0.17681, 0.27684 |
| 4 inner | 27,729 / 27,729 / 27,729 | 1,390 / 2,075 / 1,785 | 0.18213, 0.28472 |
| 4 outer | 29,496 / 29,495 / 29,496 | 4,564 / 4,382 / 2,654 | 0.18312, 0.28486 |

The changing later distributions are expected financial regime shift, not a
reason to rebalance labels with future information. In particular, Fold 1 and
Fold 3 inner validation are heavily High-risk. Macro F1 and per-class recall
are therefore more informative than accuracy.

## How future knowledge is blocked

### 1. Features stop at the prediction session

Market features use the current adjusted close/volume and trailing `shift` or
`rolling` windows. Cross-sectional ranks use only other stocks on the same
session. The feature allowlist excludes targets, split fields, and
`target_window_end`. Missing histories are rejected rather than imputed from
later rows.

### 2. Targets look forward, but training rows are purged

The target at date `t` uses sessions `t+1` through `t+20`. A row can enter a
training role only when `target_window_end < first evaluation session`. For
example, Fold 1 outer training ends at decision date 2020-05-28, whose target
window ends 2020-06-25; outer evaluation begins 2020-06-26. The protocol
records 1,000 purged company-date rows at each outer boundary.

This strict inequality is important: no training label contains a price from
the evaluation period.

### 3. Hyperparameters use inner validation only

For each outer fold, `C` or `max_leaf_nodes` is selected on the earlier inner
validation block. The chosen pipeline is then refit on the outer training rows.
Outer outcomes score the result once and do not select that fold's setting.

### 4. Preprocessing and labels are fitted on training rows

`StandardScaler` is inside the Logistic Regression pipeline, and `fit` receives
only `x_train`. Risk tertile boundaries come from that role's training future
volatility outcomes and are then applied unchanged to validation/evaluation.
HistGradientBoosting has `early_stopping=false`, avoiding an undocumented
random internal validation split.

### 5. Previously inspected periods are identified

The 2024-2025 period starts at 2024-07-01 and is excluded from all four Phase 7
development folds. The later 2026 reserved period was frozen before benchmark
evaluation. However, because the selected AI candidates were not the frozen
procedures tested there, 2026 is now viewed data and cannot be called their
untouched test.

## Overfitting controls and remaining risks

Controls already present:

- small, frozen hyperparameter grids;
- only two classical estimator families;
- chronological nested tuning rather than random shuffling;
- four outer periods rather than promoting one good period;
- comparison with simple controls and fold-consistency/safety rules;
- deterministic class order, seeds, ties, and artifact hashes;
- no fitted SEC or sentiment fields.

Risks that still remain:

1. **Researcher overfitting:** feature groups and model choices were repeatedly
   reviewed on the same four development folds.
2. **Candidate override:** the selected AI candidates failed an original
   promotion safeguard. The team may use them, but must not erase that fact.
3. **No untouched AI-model test:** current evidence is development-only.
4. **Overlapping labels:** adjacent 20-session outcomes overlap, so row counts
   exaggerate the number of independent observations.
5. **Cross-company dependence:** 50 rows from one date share market conditions.
6. **Survivorship bias:** the universe contains companies known today.
7. **Provider limitations:** adjusted-price history can drift with later
   corporate-action adjustments; IEX volume is not consolidated SIP volume.
8. **Final-fit ambiguity:** fold-selected hyperparameters differ, so Phase 9
   must freeze a new training-only selection rule rather than choose the most
   attractive fold setting.

## Mandatory conditions before freezing 9.2

The Phase 9.2 contract should not be approved unless it specifies:

1. the exact final fitting end date and a target-window purge after it;
2. a fixed inner-validation interval and metric for final hyperparameter
   selection;
3. training-only scaling and training-only risk cutoffs;
4. exact feature order, class order, probability semantics, and missing-input
   rejection;
5. a pre-fit report containing per-role dates, row counts, ticker counts, class
   distributions, and maximum target-window end;
6. assertions that no fit/tune row overlaps the selected future evaluation
   interval;
7. development-only status unless a new untouched period is reserved;
8. model selection, Shariah screening, and portfolio logic kept separate; and
9. student-run fitting through a Local/Colab portable notebook, with reusable
   tested logic under `src/`.

## Evidence reviewed

- `reports/model_evaluation/phase7_candidate_tuning_v1/handoff_validation.json`
- `reports/model_evaluation/phase7_candidate_tuning_v1/runner_validation.json`
- `reports/model_evaluation/phase7_candidate_tuning_v1/experiment_contract.json`
- `reports/model_evaluation/phase6_phase5_continuation_v1/chronological_evaluation_protocol.json`
- Phase 7 candidate reports and outer predictions
- `src/model_training/chronological_evaluation_protocol.py`
- `src/model_training/phase7/contract.py`
- `src/model_training/phase7/runner.py`
- `src/model_training/feature_ablation/ablation_runner.py`
- `src/feature_engineering/market_features.py`
- `src/feature_engineering/phase6_expansion_features.py`
- `src/target_engineering/build_modeling_dataset.py`

This audit reviews the recorded evidence and implementation. It does not claim
that financial generalization can be guaranteed or that leakage is impossible
outside the reviewed paths.
