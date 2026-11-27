# SEC point-in-time repair

## The old gap

The old folder had one current Company Facts file for each stock, but not a
complete dated package containing the matching SEC filing/submissions evidence
for every company. Therefore the project correctly excluded SEC fields from the
return and risk model. This does not mean the old figures were automatically
wrong; it means their historical proof was incomplete.

## What this repair adds

The collector creates one new dated folder under `data/raw/sec_snapshots/`.
It saves the SEC ticker list, Company Facts, submissions records, older
submissions-list pages, checksums, source URLs, download time, and failures.
It never overwrites older raw files. The large raw folder remains local and is
not pushed to GitHub.

## Timing rule

A report may describe June, but it cannot be used by the model until the day
after it was filed with SEC. For example, Apple's Q3 report filed on 31 July is
eligible from 1 August, or the next market session when 1 August is closed.

## What remains unapproved

After a successful collection, only total assets and unrestricted cash are
candidate concepts for later review. Debt, revenue, receivables, net income,
market capitalization, cash-to-assets, and every Shariah decision still need
separate checks. Downloading data alone does not improve a model.

## Run after this code is on GitHub

From the HalalifyAI folder in PowerShell:

```powershell
$env:SEC_USER_AGENT = "HalalifyAI FYP your-email@example.com"
python -m src.data_pipeline.collect_sec_point_in_time_snapshot
```

The collector prints a new folder name. Copy it into:

```powershell
python -m src.data_pipeline.validate_sec_point_in_time_snapshot data/raw/sec_snapshots/NEW_FOLDER_NAME
```

Success means the output says `"status": "passed"`. If it fails, do not use
the new snapshot for model training; inspect the printed missing-file or
checksum message first.
