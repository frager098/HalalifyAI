# Phase 7 candidate-tuning runbook

## Purpose and current status

Phase 6 is complete. Phase 7 may compare and tune only the candidates frozen in
`configs/phase6_feature_freeze_v2.json`. This runbook defines the handoff and
execution order before any Phase 7 model is fitted. It does not contain Phase 7
performance results.

The four chronological folds are development folds. They have already been
used during feature selection and are not an untouched test. Phase 7 may use
them for controlled model development, but Phase 8 still requires a genuinely
later verified period frozen before its outcomes are inspected.

## What the friend needs

First, commit and push all reviewed source, configuration, tests, notebooks,
and documentation on `feature/model-evaluation`. Give the friend the exact
commit identifier. The friend should clone or pull that commit rather than
receiving loose Python files.

Generated datasets and reports are Git-ignored, so transfer the artifacts
listed in `configs/phase7_handoff_v1.json` separately. The minimum runtime input
is the expanded CSV, its metadata, and the chronological protocol. The two
expansion summaries and five continuation summaries are also required as the
auditable justification for the v2 freeze.

Do not share `.env`, credentials, virtual environments, provider downloads, or
the friend's historical `results/` experiment as active Phase 7 input.

## Instructions for the collaborator

Use the student's completed Phase 6 artifacts. Do **not** generate a personal
replacement dataset.

1. Clone `feature/model-evaluation` and checkout the exact commit supplied by
   the student. Do not begin from an older local copy.
2. Copy the transferred `data/` and `reports/` directories into the repository
   root using the structure below.
3. Treat
   `data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv`
   as the only approved Phase 7 dataset. Its required SHA-256 is
   `99957129c288d90f63539577f707f0e04d9ad1be3a847e929b9e54e51e2ba9b0`.
4. Do not run the Phase 3 dataset builder, Phase 5 data restoration, Phase 6
   continuation notebooks, Phase 6 expansion notebook, or
   `build_phase6_expanded_dataset.py`. Those steps are complete.
5. Do not substitute `phase6_recovery_v1`, the historical `results/` folder,
   a newly downloaded Alpaca dataset, or a locally reconstructed protocol.
6. Run only the Phase 7 no-fit handoff validation first. It must verify every
   artifact against `configs/phase7_handoff_v1.json` before model fitting.
7. If a required file is missing or its hash differs, stop and request a fresh
   copy of the handoff package from the student. Do not repair, rewrite, or
   regenerate it locally.
8. Write every new artifact only under
   `reports/model_evaluation/phase7_candidate_tuning_v1/`. Never overwrite a
   Phase 5 or Phase 6 dataset/report directory.

The collaborator may implement and run Phase 7 reusable model code and
notebooks after the handoff validation passes. Any proposed change to the
frozen features, folds, estimator families, tuning budget, or metrics must be
reviewed and versioned before results are viewed.

Running a notebook normally changes its saved cell output. This is allowed.
The Phase 7 handoff check verifies the frozen Phase 7 code and settings instead
of treating notebook output changes as a failure. It still stops if that code
or those settings differ from the checked-out commit.

## Required directory structure

The transfer package should reproduce repository-relative paths exactly:

```text
HalalifyAI_phase7_handoff_v1/
├── data/
│   └── processed/
│       └── model_inputs/
│           └── phase6_expanded_features_v1/
│               ├── market_features_and_labels.csv
│               └── dataset_metadata.json
└── reports/
    └── model_evaluation/
        ├── phase6_phase5_continuation_v1/
        │   ├── momentum_ablation/
        │   │   └── momentum_ablation_summary.json
        │   ├── volatility_ablation/
        │   │   └── volatility_ablation_summary.json
        │   ├── downside_trend_ablation/
        │   │   └── downside_trend_ablation_summary.json
        │   ├── market_relative_ablation/
        │   │   └── market_relative_ablation_summary.json
        │   └── volume_ablation/
        │       └── volume_ablation_summary.json
        └── phase6_market_feature_expansion_v1/
            ├── chronological_evaluation_protocol.json
            ├── expansion_validation.json
            ├── cross_sectional_relative_strength/
            │   └── cross_sectional_relative_strength_summary.json
            └── market_regime/
                └── market_regime_summary.json
```

After cloning the exact repository commit, copy the contents of
`HalalifyAI_phase7_handoff_v1/` into the repository root. For example, the CSV
must end at
`HalalifyAI/data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv`.
Do not add another package-directory level inside the repository and do not put
the files under `results/`.

The transfer package is input evidence, not a script bundle. The repository
commit supplies the code and tracked contracts; the package supplies the
Git-ignored dataset, protocol, and Phase 6 summaries.

## Frozen candidates and comparators

### Return

- Comparator: original 14 Phase 5 market features.
- Candidate: those 14 features plus the three cross-sectional peer-rank
  features, for 17 total.
- Simple benchmark: `momentum_20d` ranking on the same dates and eligible rows.
- Primary metric: mean same-date Spearman rank correlation.
- Required secondary review: macro F1, per-class precision/recall, ordinal
  error, top-10 minus universe return, and fold variation.

The experiment supports the complete 17-feature augmentation. It does not
support silently testing the peer-rank columns alone or adding market-regime
features.

### Risk

- Comparator: original 14 Phase 5 market features.
- Candidate: the seven frozen volatility and downside/trend features.
- Simple benchmark: trailing `volatility_20d` converted with that fold's
  training-only risk cutoffs.
- Primary metric: macro F1.
- Required safety review: High-risk recall, High outcomes predicted Low,
  ordinal error, confusion matrix, log loss, Brier score, and fold variation.

The seven-feature combination was not directly refit in Phase 6. Phase 7 must
therefore compare it with the 14-feature comparator rather than assume it wins.

## Fixed model and tuning budget

Use only the estimator families and budget already recorded in the protocol:

- Logistic Regression: `C` in `0.1`, `1.0`, `10.0`; scaling fitted on training
  rows only.
- HistGradientBoosting: `max_leaf_nodes` in `15`, `31`, `63`, with
  `max_iter=100`, `learning_rate=0.1`, `early_stopping=False`, and
  `random_state=42`.

For every task, estimator, candidate, and fold:

1. choose the hyperparameter only on inner training/validation;
2. refit that selected configuration on the outer-training rows;
3. evaluate the outer block once;
4. preserve identical rows for comparator and candidate; and
5. never use the reused period beginning 2024-07-01 for selection.

No extra parameter, feature, imputation rule, calibration method, estimator, or
evaluation date may be introduced after viewing results without a new
versioned contract.

## Small execution steps

### 7.1 Receive and validate the handoff — no fitting

Verify the exact source-control commit, every artifact path and checksum,
dataset schema, 124,987 ordered rows, 118,987 eligible rows per task, feature
allowlist, four protocol folds, and v2 freeze. Stop on any mismatch.

**Planned output:**
`reports/model_evaluation/phase7_candidate_tuning_v1/handoff_validation.json`.

### 7.2 Freeze the Phase 7 experiment contract — no fitting

Record both task feature lists, comparators, estimator families, parameter
grids, metrics, tie rules, fold identities, risk guardrails, benchmarks, and
the rule for choosing or declining a learned candidate. The contract must be
written before model results exist.

**Planned output:**
`reports/model_evaluation/phase7_candidate_tuning_v1/experiment_contract.json`.

### 7.3 Validate the reusable runner — no fitting

Add focused tests for allowlists, matched rows, chronology, target-window
purging, training-only scaling and risk cutoffs, inner-only tuning, disabled
tree early stopping, deterministic ties, output provenance, and overwrite
refusal.

**Successful output:** all focused tests pass and
`runner_validation.json` reports `model_fitting_performed: false`.

### 7.4 Tune and evaluate return Logistic Regression

Evaluate the 14-feature comparator and 17-feature candidate on identical rows.
Choose `C` inside each inner fold and score the outer fold once. Include the
momentum benchmark on the same evaluation dates.

**Planned output:** `return/logistic_regression/` with fold-level runs and one
paired summary.

### 7.5 Tune and evaluate return HistGradientBoosting

Repeat Step 7.4 with the three frozen leaf-node choices and fixed tree settings.
Do not change the features after seeing Logistic Regression results.

**Planned output:** `return/hist_gradient_boosting/`.

### 7.6 Review and freeze the return development choice — no new fitting

Compare both learned estimators, both feature sets, and momentum across folds.
Prefer no learned model if improvement is inconsistent. Do not choose solely
from the average or one favorable period.

**Planned output:** `return/return_candidate_summary.json` with a documented
advance or benchmark-retention decision.

### 7.7 Tune and evaluate risk Logistic Regression

Compare the original 14 features with the seven-feature candidate on identical
rows, using fold-specific training cutoffs and inner-selected `C`.

**Planned output:** `risk/logistic_regression/`.

### 7.8 Tune and evaluate risk HistGradientBoosting

Repeat Step 7.7 with the frozen tree grid. Preserve High-risk recall and
High-to-Low errors in every fold report.

**Planned output:** `risk/hist_gradient_boosting/`.

### 7.9 Review and freeze the risk development choice — no new fitting

Compare learned candidates with the original 14-feature comparator and trailing
volatility benchmark. A macro-F1 gain cannot hide materially worse High-risk
recall or additional High-to-Low mistakes. Record whether a learned candidate,
the 14-feature model, or the simple benchmark advances.

**Planned output:** `risk/risk_candidate_summary.json`.

### 7.10 Publish the Phase 7 conclusion — no extra search

Create the final Phase 7 report and versioned freeze containing exact features,
estimator, hyperparameters, training rules, evidence hashes, limitations, and
the Phase 8 gate. Preserve failures and inconclusive outcomes.

**Planned outputs:** `phase7_summary.json`, a tracked Phase 7 freeze config, and
an evaluator-facing Markdown report.

## Student-run notebook order

Phase 7 should use small notebooks that call reusable modules under
`src/model_training/`; the notebooks should not duplicate training logic.
Prepare and run them in this order:

1. `phase7_handoff_and_runner_validation.ipynb` — Steps 7.1–7.3.
2. `phase7_return_logistic.ipynb` — Step 7.4.
3. `phase7_return_hist_gradient_boosting.ipynb` — Step 7.5.
4. `phase7_return_review.ipynb` — Step 7.6, no fitting.
5. `phase7_risk_logistic.ipynb` — Step 7.7.
6. `phase7_risk_hist_gradient_boosting.ipynb` — Step 7.8.
7. `phase7_risk_review.ipynb` — Step 7.9, no fitting.
8. `phase7_final_report.ipynb` — Step 7.10, no additional search.

These entry points are implemented in `src/model_training/phase7/`, covered by
focused tests, and ready for student execution after the source commit is
pushed. They have not yet produced Phase 7 model results. Each notebook writes
new-only output and refuses to overwrite prior evidence.
