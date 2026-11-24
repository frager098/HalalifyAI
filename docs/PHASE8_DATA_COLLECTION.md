# Phase 8 reserved-period data collection

## Frozen period

The approved Phase 8 evaluation period is **2026-01-02 through 2026-09-30**.
It must remain separate from the Phase 3–7 development dataset and must not be
used to change features, benchmark definitions, thresholds, or selection rules.

The collection window is **2025-10-01 through 2026-10-28**. The earlier overlap
provides the trailing history required by 60-session features and permits a
continuity check against the frozen source. The later support window supplies
20 XNYS sessions after 2026-09-30 so forward labels can eventually be formed.
Neither purpose makes overlap dates part of the Phase 8 evaluation.

## Student-run extraction

1. Confirm `.env` contains `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. Do not
   commit this file.
2. Activate the project virtual environment.
3. Install the declared collection and validation dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-cleaning.txt
   ```

   This installs the Alpaca HTTP client, `.env` loader, pandas, and the XNYS
   exchange calendar used by the coverage check. It does not download market
   data.
4. Run:

   ```powershell
   .\.venv\Scripts\python.exe -m src.data_pipeline.download_phase8_market_data
   ```

The command reads `configs/phase8_market_data_collection_v1.json`. It requests
the same 50 companies plus SPY from Alpaca SIP using both `adjustment=split`
and `adjustment=all`. It writes a new immutable directory under
`data/raw/phase8_market/phase8_alpaca_sip_<UTC timestamp>/`; it does not read or
overwrite the earlier processed model dataset.

Successful output contains:

- raw paginated `split_*.json` and `all_*.json` responses;
- `daily_prices.csv`, containing split-adjusted OHLC/volume and all-adjusted
  close;
- `coverage_validation.json`, containing dates and coverage only;
- `metadata.json`, containing request provenance and SHA-256 hashes.

Step 8.1 passes only when `coverage_validation.json` reports `passed: true` and
`outcomes_inspected: false`, and the separate cleaning acceptance below also
passes. Do not build labels, inspect future returns or future volatility, or
score the frozen benchmarks during this collection step.

## Student-run cleaning and acceptance

After the raw coverage check passes, run:

```powershell
.\.venv\Scripts\python.exe -m src.data_pipeline.clean_phase8_market_data
```

This command reads `configs/phase8_cleaning_v1.json` and writes only to:

```text
data/processed/phase8_market_cleaned/
└── phase8_alpaca_sip_20261124T005018Z_cleaned_v1/
```

It validates raw hashes, reconciles normalized rows with both raw adjustment
snapshots, quarantines invalid values, checks the XNYS calendar, compares the
October–December 2025 overlap with the frozen earlier cleaned source, verifies
all 187 evaluation sessions, and freezes accepted-output hashes. It creates no
labels or outcome summaries.

Successful output includes `acceptance_report.json` with `accepted: true`,
`outcomes_inspected: false`, and `labels_created: false`; `accepted_snapshot.json`
then records the accepted cleaned CSV and evidence hashes. If any required gate
fails, the command writes `FAILED.json` and does not freeze the snapshot.
