# Phase 9.1: Predictor handoff decision v1

**Decision date:** 2026-11-27  
**Status:** AI model candidates selected; final fitting and packaging still required  
**Decision source:** the project-team instruction to use the best learned models
from the completed earlier-phase comparisons and not use the simple
`momentum_20d` or `volatility_20d` procedures as Phase 9 predictors

## Decision

Phase 9 will use these learned candidate specifications:

| Task | Selected AI model | Declared primary metric | Development result |
| --- | --- | --- | --- |
| Return | Logistic Regression, Phase 7 candidate feature set | Mean same-date Spearman from `P(Higher) - P(Lower)` | `0.03385821402286833` |
| Risk | HistGradientBoosting, Phase 7 candidate feature set | Macro F1 | `0.5706164300714849` |

These were the strongest learned candidates by each task's predeclared primary
metric. The earlier simple procedures remain research comparators only. They
must not be packaged as the Phase 9 return or risk predictor.

## Exact candidate specifications

### Return model

The return candidate is multinomial Logistic Regression with a `StandardScaler`
fit only on eligible training rows, `solver="lbfgs"`, and `max_iter=1000`.
Its 17 ordered inputs are:

1. `return_1d`
2. `momentum_5d`
3. `momentum_20d`
4. `momentum_60d`
5. `volatility_20d`
6. `volatility_60d`
7. `downside_dev_20d`
8. `drawdown_from_peak_60d`
9. `price_to_sma20`
10. `price_to_sma50`
11. `volume_ratio_20d`
12. `spy_momentum_20d`
13. `excess_momentum_20d`
14. `market_beta_60d`
15. `return_5d_peer_rank`
16. `momentum_20d_peer_rank`
17. `momentum_60d_peer_rank`

It predicts `Lower`, `Middle`, and `Higher` return classes. Its ranking score is
`P(Higher) - P(Lower)`, not an expected percentage return.

The four chronological development folds selected `C` values `0.1`, `10.0`,
`10.0`, and `0.1` through inner validation. Therefore Phase 9 must not guess a
single final `C`. A frozen final-fit rule must select it using training-only
inner validation before an artifact is produced.

### Risk model

The risk candidate is `HistGradientBoostingClassifier` with `max_iter=100`,
`learning_rate=0.1`, `early_stopping=false`, and `random_state=42`. Its seven
ordered inputs are:

1. `volatility_20d`
2. `volatility_60d`
3. `return_1d`
4. `downside_dev_20d`
5. `drawdown_from_peak_60d`
6. `price_to_sma20`
7. `price_to_sma50`

It predicts `Low`, `Medium`, and `High` future realized-volatility classes.
Class boundaries must be calculated from eligible training outcomes only and
saved with the fitted artifact.

The four chronological development folds selected `max_leaf_nodes` values
`63`, `15`, `15`, and `31`. Phase 9 must select the final value using a frozen
training-only rule rather than choosing one after viewing later outcomes.

## Evidence limits that remain mandatory

This team decision changes which procedures Phase 9 intends to package; it does
not rewrite the earlier evidence or turn a rejected candidate into a validated
production model.

- The return candidate beat the comparator on only two of four folds, so it
  failed the predeclared three-fold consistency gate.
- The risk candidate improved macro F1 in all four folds and had nine fewer
  total High-to-Low errors, but mean High-risk recall was `0.6327255825108913`,
  below the comparator's `0.6568623393589013`. It failed that safety gate.
- The reserved 2026 evaluation measured the simple comparators, not these AI
  models. Its scores cannot be attributed to these models.
- The exploratory Kronos experiment did not follow the full approved protocol
  and is not selected for either task.
- No final estimator, scaler, final hyperparameter, or deployable model binary
  currently exists.

Accordingly, both selected AI models are **development-evidence candidates**.
User-facing output must show that status until a separately approved evaluation
supports a stronger claim.

## Phase 9 packaging gate

The first AI-model inference release requires trained model artifacts and class
probabilities. Before packaging, Phase 9 must add a student-run, Local/Colab
portable final-fit notebook that:

1. freezes the eligible fitting dates and the inner-validation rule;
2. fits the scaler and return model on training data only;
3. calculates risk class boundaries from training outcomes only;
4. fits the risk model on training data only;
5. saves model, preprocessing, feature order, class order, boundaries,
   dependency versions, dataset/code identities, and fitting metadata; and
6. does not describe the already viewed 2026 period as an untouched test of
   these changed procedures.

Codex must prepare this workflow with reusable logic under `src/`, but the
student must run the fitting notebook. Steps 9.2 and later must not fall back to
the two simple comparator rules if a fitted artifact is missing.

## Still unsupported

- expected percentage-return prediction;
- a claim that either model passed all original promotion rules;
- an untouched-test result for these selected AI models;
- approved SEC fundamental predictors;
- Shariah compliance, portfolio performance, or trading performance.

## Evidence identities reviewed

| Evidence | SHA-256 |
| --- | --- |
| `reports/model_evaluation/phase7_candidate_tuning_v1/experiment_contract.json` | `d817a11916228a2af9709daf78dbfca0ecc150f5ab3d45155fed84fd2c42d8fa` |
| `reports/model_evaluation/phase7_candidate_tuning_v1/phase7_summary.json` | `3d297b7a1dc30b850b337539ca44229093262c206f35753d2ceb127e9d411c3b` |
| `reports/model_evaluation/phase7_candidate_tuning_v1/return/logistic_regression/candidate_report.json` | `2517e4b4e489edfda96534fcc2e9877fb6c10ce2ca28ee27b5cac28f82f44d4e` |
| `reports/model_evaluation/phase7_candidate_tuning_v1/risk/hist_gradient_boosting/candidate_report.json` | `903de0f71b9c80009b4cfb4874bd5ce4f8f6343ae1c36a51fea0051391056919` |

This decision runs no fitting or evaluation. The next work is to revise and
freeze the Phase 9 inference/final-fit contract around these two AI models.
