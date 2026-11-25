# Notebooks

## Phase 6 continuation in Google Colab

The active Phase 6 notebooks continue the exact dataset used by the student's
Phase 5 execution. In Colab, the setup cell clones the
`feature/model-evaluation` branch into `/content/HalalifyAI`, installs pinned
dependencies, and restores the Git-ignored Phase 5 CSV from the same public
artifact folder used by `model_evaluation_report.ipynb`. It does not mount
Google Drive.

Run `phase6_phase5_continuation_setup.ipynb` first. It verifies dataset
`71bbe368...`, reproduces chronological protocol `048d82ce...`, creates the
Phase 6.2 inventory, and performs the no-fit Phase 6.3 validation. All new
evidence is written under:

`reports/model_evaluation/phase6_phase5_continuation_v1/`

The friend's separate recovery experiment remains preserved under the local,
Git-ignored `results/` folder and is never overwritten. Colab's `/content`
storage is temporary, so download the completed continuation report folder
before ending the runtime.

## Notebook roles and order

- `model_evaluation_report.ipynb` is the Phase 5 evaluator-facing notebook.
- `phase6_phase5_continuation_setup.ipynb` performs Steps 6.2 and 6.3 without
  model fitting.
- `phase6_momentum_ablation.ipynb` performs Step 6.4 and writes the continuation
  momentum evidence.
- `phase6_volatility_ablation.ipynb` performs Step 6.5 and writes the
  continuation volatility evidence.
- `phase6_downside_trend_ablation.ipynb` performs Step 6.6 and writes the
  continuation downside/trend evidence.
- `phase6_market_relative_ablation.ipynb` performs Step 6.7, including the daily
  SPY-alignment check.
- `phase6_volume_ablation.ipynb` performs Step 6.8 and retains the Alpaca IEX
  volume limitation.
- `feature_ablation_report.ipynb` is a read-only historical workflow guide.
- `phase6_recovery_validation.ipynb` belongs to the friend's historical recovery
  experiment and is not part of the continuation run.
- `legacy/` contains earlier baseline, Colab, and embedded data-cleaning
  notebooks retained for historical comparison.

Each fitting notebook refuses to overwrite its existing continuation output.
Reusable data and model logic belongs in `src/`; notebooks call those modules
instead of maintaining separate implementations.

## Phase 6.9 controlled expansion

The student completed `phase6_market_feature_expansion.ipynb` after preserving
all five continuation comparisons. Its formulas and decision rules were frozen
before execution in
`configs/phase6_market_feature_expansion_v1.json` and explained in
`docs/PHASE6.md`.

The notebook creates a separate
`data/processed/model_inputs/phase6_expanded_features_v1/` dataset. It compares
the original 14 features with the exact same rows plus one new three-feature
group at a time: cross-sectional relative strength, then SPY market regime.
Return and risk are evaluated separately across the four frozen chronological
folds. Generated evidence is written only under
`reports/model_evaluation/phase6_market_feature_expansion_v1/`.

The reviewed outcome is frozen in `configs/phase6_feature_freeze_v2.json` and
documented in `docs/PHASE6.md`. Phase 7 must use only those
task-specific candidates and their declared baselines.

## Phase 7 status

The Phase 7 workflow and friend handoff are specified in
`docs/PHASE7_RUNBOOK.md` and `configs/phase7_handoff_v1.json`. The planned work
is split into eight small student-run notebooks covering handoff/runner
validation, two return estimators, return review, two risk estimators, risk
review, and the final report.

The eight notebooks and reusable modules are now implemented. After pulling the
reviewed source commit and placing the transferred Phase 6 artifacts at their
exact repository-relative paths, run them in this order with the existing
`.venv` Python 3.12 kernel:

1. `phase7_handoff_and_runner_validation.ipynb` (Steps 7.1-7.3, no fitting)
2. `phase7_return_logistic.ipynb` (Step 7.4)
3. `phase7_return_hist_gradient_boosting.ipynb` (Step 7.5)
4. `phase7_return_review.ipynb` (Step 7.6, no fitting)
5. `phase7_risk_logistic.ipynb` (Step 7.7)
6. `phase7_risk_hist_gradient_boosting.ipynb` (Step 7.8)
7. `phase7_risk_review.ipynb` (Step 7.9, no fitting)
8. `phase7_final_report.ipynb` (Step 7.10, no fitting)

Every step writes new-only evidence. Do not rerun Phase 3, Phase 5, or Phase 6
preparation and do not delete an earlier output merely to obtain a preferred
result.

## Phase 8 reserved evaluation and review

- `phase8_one_time_evaluation.ipynb` performs the one-time Step 8.6 scoring.
  Do not rerun it after the frozen result exists.
- `phase8_step_8_7_review.ipynb` compares that result with the retained Phase 7
  benchmark evidence without fitting or tuning. In the Colab browser it asks
  for one `phase8_step_8_7_inputs.zip`; its final cell downloads
  `phase8_step_8_7_results.zip`.

The exact upload contents and Colab run order are documented in
`docs/phase8/DATASET_AND_NOTEBOOK_RUNBOOK.md`.
