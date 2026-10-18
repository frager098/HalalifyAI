# Run cleaning and create modeling targets

The existing modeling CSV is ready for the planned modeling workflow; you do not need to repeat cleaning just to use it. Keep its accompanying `targets_metadata.json` and `README.md`.

To recreate cleaned tables from the preserved raw snapshots and interim price input, open `HalalifyAI_Data_Cleaning.ipynb` in this folder and choose Run All. Section 7 creates both targets in a new modeling CSV. In Colab, mount Drive and set ROOT to this folder's copy while preserving the data directory structure.

Alternatively, use the project Python environment:

```powershell
.\.venv\Scripts\python.exe clean_data.py --root .
```

Cleaning writes a new `data/cleaned/<run_id>/` folder. Then pass that run's `prices_clean.csv` to the target generator:

```powershell
.\.venv\Scripts\python.exe create_targets.py --prices "data/cleaned/<run_id>/prices_clean.csv"
```

Replace `<run_id>` with the directory printed by cleaning. The target generator writes a new `data/modeling/<run_id>/` directory. Neither step changes preserved source data or prior modeling runs. If rebuilding the environment, install `requirements-cleaning.txt` first.

The cleaning loop repeats safe normalization and validation until table hashes stop changing. It preserves SEC units, reporting periods and filing versions, separates invalid or conflicting records, and reports unresolved evidence. No missing prices are fabricated and no large returns are clipped. Use only completed cleaning runs containing `report.json`.

Risk is annualized sample volatility of the next 20 trading-session simple adjusted returns. Low/medium/high classes use pooled training-only tertiles. Shared chronological splits exclude label windows crossing boundaries. Rows with incomplete future returns remain unlabeled. The modeling table contains price-based features; SEC predictors have not been joined.

For every model, exclude BOTH `risk_volatility_next_20d` and `risk_class_next_20d` from X, plus future-window and split metadata. Use the explicit feature allowlist in `targets_metadata.json`. Select the appropriate target as y. Use only train/validation/test rows, excluding purged and unlabeled rows. Fit imputation and scaling on training features only. Recompute class boundaries and purge label overlap for each training fold if changing the split or using time-series cross-validation.

Corporate-action evidence, historical issuer mappings and historical data vintages remain unresolved. These limitations are preserved in the data flags. SPY supplies a benchmark feature and is not one of the modeled companies. CIK values are identifiers; when reading SEC tables, preserve them as strings.

Validation tests:

```powershell
.\.venv\Scripts\python.exe -B -m unittest test_clean_data test_targets -v
```

Downloader code and credentials were removed. The original raw benchmark snapshots, their metadata, the required interim input, and `SOURCE.json` remain intact.
