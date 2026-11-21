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
