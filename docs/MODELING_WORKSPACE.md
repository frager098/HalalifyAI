# HalalifyAI modeling and cleaning workspace

The modeling dataset is in `data/modeling/20261009T115557984450Z/`:

- `model_dataset.csv`: price-based company rows with both risk targets and chronological splits.
- `targets_metadata.json`: target definitions, class thresholds, feature allowlist, splits and checksums.
- `README.md`: modeling usage notes.

Original benchmark snapshots are preserved in `data/raw/`. The original combined price input is preserved in `data/interim/` because the cleaner validates it against raw Alpaca responses. `SOURCE.json` records downloader provenance.

`HalalifyAI_Data_Cleaning.ipynb` contains the complete cleaning and target-generation workflow. `clean_data.py` and `create_targets.py` provide the same steps as standalone scripts. `requirements-cleaning.txt`, the existing `.venv/`, and the two test scripts support running and validating those steps.

Redundant cleaned outputs, validation reports, downloader code, downloader credentials and the notebook-building helper were removed during cleanup. No raw, interim or modeling data was changed.

See `CLEANING_README.md` for execution instructions. Both target columns must be excluded from model input features for every task. The source's unresolved corporate-action and historical identity checks still apply.
