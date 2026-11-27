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

## Kronos-small exploratory smoke test

`kronos_small_smoke_test.ipynb` loads the upstream Kronos-small checkpoint and
forecasts 20 AAPL sessions from a 90-session OHLCV history. Its one-date raw
close comparison is a diagnostic, **not** a Phase 8 score or a new blind test.
It preserves the frozen Phase 8 artifacts and writes one new JSON file under
`reports/model_evaluation/kronos_small_smoke_v1/`.

Local setup, using the same Python environment selected as the notebook kernel:

```powershell
.\.venv\Scripts\python.exe -m pip install "torch>=2.0" einops==0.8.1 huggingface_hub==0.33.1 safetensors==0.6.2 pandas numpy
```

In the first notebook cell, check `sys.executable`. If it is not the
repository's `.venv` Python, select the `.venv` kernel in Jupyter and restart
the notebook. Installing into one Python environment does not install packages
into another kernel. The current local `.venv` uses Python 3.14.8; the command
above targets that environment specifically.

Open the notebook and run its cells from top to bottom. It needs the accepted
`prices_clean.csv` at the path in
`configs/phase8_evaluation_contract_v1.json`. The preflight checks its SHA-256
before downloading the checkpoint. The notebook clones a fixed upstream
Kronos commit into ignored `data/interim/kronos_upstream/`, loads fixed
Hugging Face model and tokenizer revisions, and sets a sampling seed. If an
existing interim clone is at another commit, use a fresh interim clone.

For Colab, first make the notebook available in the cloned repository. Prepare
one `kronos_small_inputs.zip` containing only the accepted `prices_clean.csv`
at its full repository-relative path. Run the cells in order: the preflight
cell prompts for the ZIP, validates its contents, extracts it into the cloned
repository, and checks the frozen input hash. The setup cell installs only
this notebook's Python packages.
Download the JSON result before ending the Colab session; Colab storage is
temporary. A fresh run refuses to overwrite an existing result.

## Phase 9 tuning comparison

Open `phase9_tuning_comparison.ipynb` with the repository's Python environment.
Run setup, preflight, comparison, then review/export cells in order. Preflight
reads `configs/phase9_experiment_protocol_v1.json` and verifies the Phase 6
dataset and chronological protocol hashes. The comparison fits only on
development folds and creates new files under
`reports/model_evaluation/phase9_tuning_v1/`; an existing output directory
causes an error rather than an overwrite. The student should inspect all four
folds before selecting any change.

In Colab, upload/open the notebook itself if it has not been pushed. Its setup
cell clones the existing branch. When prompted, upload `phase9_code.zip`
containing only `configs/phase9_experiment_protocol_v1.json` and
`src/model_training/phase9_experiment.py` at those repository-relative paths;
this supplies the new untracked code without staging or pushing it. Then upload
`phase9_tuning_inputs.zip` when prompted. The input ZIP must contain only the missing
Git-ignored files at their repository-relative paths: the Phase 6 expanded
`market_features_and_labels.csv`, the Phase 6 chronological protocol JSON, the
Phase 7 experiment contract JSON, and the selected return and risk candidate
report JSON files. The preflight cell prints each exact path. The final
cell downloads the generated results bundle. This is a development comparison;
it does not create final fitted artifacts or an untouched test result.

## Phase 9.2c final development fit

Open `phase9_final_fit.ipynb` and run its five cells in order: introduction,
environment setup, preflight, model fit, and result export. It reads the
frozen paths in `configs/phase9_final_fit_v1.json`. The preflight checks all
input hashes. The fit chooses Logistic Regression `C` and risk tree leaf nodes
using fold 4's chronological inner validation, then refits both models on
eligible development labels that end before 2024-07-01. It writes
`return_model.joblib`, `risk_model.joblib`, and `manifest.json` under
`reports/model_evaluation/phase9_final_fit_v1/`. A successful final cell
prints both artifact hashes. It does not produce an untouched-test score.

**Local:** open the notebook with the repository's Python kernel, then run
all cells top to bottom. The required dataset and reports must already be at
their repository-relative paths. The preflight prints any missing path.

**Colab:** upload/open the notebook itself. Its setup cell clones the project
and prompts for `tmp/phase9_final_fit_code.zip` (upload the file under the
name `phase9_final_fit_code.zip`) if the new config and runner are absent from
the clone. The preflight then prompts for
`tmp/phase9_final_fit_inputs.zip` (upload as `phase9_final_fit_inputs.zip`)
containing the six Git-ignored inputs at their repository-relative paths.
The supplied bundle contains only the dataset CSV, its metadata, the Phase 6
fold protocol, the Phase 7 experiment contract, and the two 9.2b JSON result
files. The inference contract is already tracked in Git. The last cell
downloads `phase9_final_fit_v1.zip`; retain that ZIP and share it for the
9.2c result review. Both transfer ZIPs are ignored by Git.

## Kronos-small development comparison

After the smoke test, use `kronos_small_development_comparison.ipynb` to inspect
30 preselected forecasts: 10 stocks on each of 2024-09-03, 2025-03-03, and
2025-09-02. It reads the frozen Phase 6 development CSV identified by
`configs/phase8_evaluation_contract_v1.json`, verifies its SHA-256, and uses
the same pinned Kronos code and checkpoint as the smoke test. Each case uses
90 past daily OHLCV bars and predicts 20 later daily bars. It compares raw
20-session return ranking with raw trailing momentum, and raw future realized
volatility error with raw trailing volatility. These are exploratory
development comparisons, not the adjusted-price Phase 8 metrics.

Local order: select the kernel with the Kronos dependencies (check the printed
`sys.executable`), then run notebook cells from top to bottom. The cells check
the input and dependencies, preflight all 30 cases, load Kronos, generate the
forecasts, show the comparison, and write three files under
`reports/model_evaluation/kronos_small_development_v1/`. Forecasting on CPU may
take time. The notebook refuses to overwrite an existing report.

Colab order: make the notebook available in the cloned repository, then run
the same cells. In the preflight cell upload one
`kronos_development_inputs.zip` containing only
`data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv`
at that exact repository-relative path. The cell extracts and hashes it.
Download the three generated report files before ending the Colab session.
