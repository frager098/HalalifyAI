# HalalifyAI modeling and cleaning workspace

The modeling dataset is in `data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/`:

- `model_dataset.csv`: price-based company rows with both risk targets and chronological splits.
- `targets_metadata.json`: target definitions, class thresholds, feature allowlist, splits and checksums.
- `README.md`: modeling usage notes.

Original benchmark snapshots are preserved in `data/raw/`. The original combined price input is preserved in `data/interim/` because the cleaner validates it against raw Alpaca responses. `SOURCE.json` records downloader provenance.

Current commands are modules: `python -m src.data_pipeline.validate_source_data --phase2`, `python -m src.data_pipeline.clean_source_data`, and `python -m src.legacy.target_generation.create_legacy_targets`. The last command builds legacy targets; the current modeling dataset is built by `src.target_engineering.build_modeling_dataset`. `requirements-cleaning.txt` supplies the exchange-calendar dependency. Use the commands in [CLEANING_README.md](CLEANING_README.md).

Phase 2 preserves the original inputs and adds `data/raw/alpaca/alpaca_sip_20261009T110617242394Z_restored_json_v1/`: all price pages match the original acquisition hashes after recovering compact JSON bytes. A completed market-only cleaning run and the exact eligible input are named in `reports/generated/phase2_20261022T060900192314Z/phase2_report.json`. The full data decision and remaining limitations are in [DATA_REVIEW.md](DATA_REVIEW.md). SEC predictors remain excluded; original AAPL Company Facts integrity is unresolved.

See `CLEANING_README.md` for execution instructions. Both target columns must be excluded from model input features for every task. The source's unresolved corporate-action and historical identity checks still apply.
