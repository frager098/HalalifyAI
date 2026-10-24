# Run cleaning and create modeling targets

The preserved modeling CSV is an earlier research benchmark. It does not contain the newly approved phase 1 labels. Phase 2 now provides a separate cleaned market input for the phase 3 feature/label build; see [DATA_REVIEW.md](DATA_REVIEW.md) for exact artifacts and limitations.

Run from the repository root. This command checks all original hashes, restores price pages only when their exact original digests can be reproduced, runs market cleaning, and saves the complete phase 2 evidence:

```powershell
.\.venv\Scripts\python.exe -m src.data_pipeline.validate_source_data --phase2
```

Alternatively, use the project Python environment:

```powershell
.\.venv\Scripts\python.exe -m src.data_pipeline.clean_source_data --root . --price-version alpaca_sip_20261009T110617242394Z_restored_json_v1 --market-only
```

Cleaning writes a new `data/processed/cleaned_market_data/<run_id>/` folder. To reproduce **legacy** targets, pass that run's `prices_clean.csv` to the existing target generator. This is not the phase 3 implementation of the newly approved targets:

```powershell
.\.venv\Scripts\python.exe -m src.legacy.target_generation.create_legacy_targets --prices "data/processed/cleaned_market_data/<run_name>/prices_clean.csv"
```

Replace `<run_name>` with the directory printed by cleaning. The legacy target generator writes a new timestamped directory under `data/processed/model_inputs/legacy_runs/`. Neither step changes preserved source data or prior modeling runs. If rebuilding the environment, install `requirements-cleaning.txt` first.

The cleaning loop repeats safe normalization and validation until table hashes stop changing. It preserves SEC units, reporting periods and filing versions, separates invalid or conflicting records, and reports unresolved evidence. No missing prices are fabricated and no large returns are clipped. Use only completed cleaning runs containing `report.json`.

Risk is annualized sample volatility of the next 20 trading-session simple adjusted returns. Low/medium/high classes use pooled training-only tertiles. Shared chronological splits exclude label windows crossing boundaries. Rows with incomplete future returns remain unlabeled. The modeling table contains price-based features; SEC predictors have not been joined.

For every model, exclude BOTH `risk_volatility_next_20d` and `risk_class_next_20d` from X, plus future-window and split metadata. Use the explicit feature allowlist in `targets_metadata.json`. Select the appropriate target as y. Use only train/validation/test rows, excluding purged and unlabeled rows. Fit imputation and scaling on training features only. Recompute class boundaries and purge label overlap for each training fold if changing the split or using time-series cross-validation.

Corporate-action evidence, historical issuer mappings and historical data vintages remain unresolved. These limitations are preserved in the data flags. SPY supplies a benchmark feature and is not one of the modeled companies. CIK values are identifiers; when reading SEC tables, preserve them as strings.

Validation tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_clean_data tests.test_price_reconciliation tests.test_pit_fundamentals -v
```

The original raw snapshots, metadata, interim input, and `SOURCE.json` remain intact. Legacy downloaders exist but do not reproduce this two-price-basis snapshot workflow. The default combined cleaner still rejects the original mismatched AAPL SEC files; `--market-only` validates market hashes fully and deliberately omits SEC processing. It is not a checksum bypass. Restored market sources retain unresolved corporate-action and historical-identity flags.
