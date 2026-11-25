# Phase 8: Dataset and notebook runbook

## Purpose

Step 8.3 applies the frozen contract to the accepted clean Phase 8 prices. It
creates the original 14 audited market features and the two 20-session outcomes,
then applies the frozen peer-relative return class and training-only risk
cutoffs. It does not score either benchmark or calculate performance metrics.

The output is separate from all Phase 3–7 model inputs:

`data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1/`

## Student-run command

From the repository root with the project environment active, run:

```powershell
.\.venv\Scripts\python.exe -m src.model_training.phase8.build_reserved_dataset
```

The command reads:

- `configs/phase8_evaluation_contract_v1.json`;
- the accepted Phase 8 `prices_clean.csv` named in that contract;
- the frozen pre-2026 development dataset only to revalidate the training risk
  cutoffs and Phase 7 selection identities.

It creates:

```text
data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1/
├── reserved_features_and_labels.csv
├── dataset_metadata.json
└── validation_report.json
```

Success means `validation_report.json` reports `passed: true`, exactly 9,350
rows, 50 companies, 187 sessions, 9,350 eligible rows for each task, and
`outcomes_scored: false`. The last target window must end on 2026-10-28.

Do not open or summarize the outcome columns before the Step 8.4 runner has been
validated. Do not rerun into the same directory; the builder refuses overwrite.

## Step 8.4 no-score runner validation

After Step 8.3 passes, run:

```powershell
.\.venv\Scripts\python.exe -m src.model_training.phase8.validate_runner
```

This command reads only keys, chronology, eligibility, and feature columns from
the real reserved dataset. It does not load the four reserved outcome/class
columns. Metric functions are exercised only on synthetic fixtures. Successful
output is written new-only to:

`reports/model_evaluation/phase8_reserved_evaluation_v1/runner_validation.json`

Success requires `status: passed`, `reserved_outcome_values_read: false`,
`model_fitting_performed: false`, and
`performance_metrics_calculated_on_reserved_period: false`.

## Step 8.6 one-time evaluation notebook

Use `notebooks/phase8_one_time_evaluation.ipynb`. Run every cell once in order.
The notebook refuses to overwrite an existing evaluation result.

### Local Python

Open the notebook from anywhere inside the repository. Its setup cell locates
the repository root automatically. The preflight expects the Step 8.3 dataset
files and Step 8.4 runner validation at their existing repository-relative
paths.

### Google Colab

First commit and push the complete Phase 8 code on
`feature/model-evaluation`. Open or upload the notebook and run from the first
cell. It clones that branch into `/content/HalalifyAI`, verifies the required
tracked code, and installs the declared requirements. Use Colab's left **Files**
sidebar to upload these four files directly into `/content`:

If `/content/HalalifyAI` already exists, the setup cell fetches, checks out, and
fast-forwards `feature/model-evaluation` before the code preflight.

1. `reserved_features_and_labels.csv`
2. `dataset_metadata.json`
3. `validation_report.json`
4. `runner_validation.json`

Rerun the preflight cell after the sidebar uploads finish. It copies each file
from `/content` to the correct repository-relative path and then runs the same
preflight and evaluation logic as local Python. This avoids Colab's occasionally
unresponsive `files.upload()` widget.

Successful execution creates exactly one new file:

`reports/model_evaluation/phase8_reserved_evaluation_v1/one_time_evaluation.json`

Do not delete or overwrite it to rerun the same reserved evaluation.

## Step 8.7 non-tuning review notebook

Use `notebooks/phase8_step_8_7_review.ipynb`. This notebook compares the
retained Phase 7 simple benchmarks with the single Phase 8 reserved result. It
does not fit a model, reopen selection, or create a post-hoc performance gate.

### Create the one-file Colab upload bundle

From the repository root in PowerShell, create the small input bundle:

```powershell
tar -a -c -f phase8_step_8_7_inputs.zip `
  reports/model_evaluation/phase7_candidate_tuning_v1/phase7_summary.json `
  reports/model_evaluation/phase7_candidate_tuning_v1/return/logistic_regression/comparator_report.json `
  reports/model_evaluation/phase7_candidate_tuning_v1/risk/logistic_regression/comparator_report.json `
  reports/model_evaluation/phase8_reserved_evaluation_v1/one_time_evaluation.json
```

The ZIP must keep those repository-relative paths. It contains no raw dataset,
credentials, or model binary.

### Google Colab browser run order

1. Commit and push the Step 8.7 source files to `feature/model-evaluation`.
2. Open `phase8_step_8_7_review.ipynb` in the Colab browser.
3. Run the first setup code cell. It clones or fast-forwards the branch.
4. Run the next upload code cell. When the browser picker appears, choose only
   `phase8_step_8_7_inputs.zip`.
5. Run the remaining cells in order. The preflight checks all four SHA-256
   identities before producing a review.
6. The final cell downloads `phase8_step_8_7_results.zip` automatically.

Successful execution creates these new-only files inside the downloaded ZIP:

```text
reports/model_evaluation/phase8_reserved_evaluation_v1/
├── step_8_7_review.json
└── step_8_7_review.md
```

Extract the downloaded ZIP into the local repository root without renaming its
directories. Do not rerun after those outputs exist; the review refuses to
overwrite them.
