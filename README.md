# HalalifyAI

Latest screening repair: [free-source repair and remaining gaps](docs/screening_source_repair_20261024.md).
The V7 historical 2025 screen has **22 rule failures, 28 undecided stocks and 0 complete passes**.
Read [all 50 results](reports/screening/ftse_yasaar_2025_v7/results.md) or
[the per-stock data gaps](reports/screening/ftse_yasaar_2025_v7/data_gaps.csv).

Python AI service for Halalify.

The service will provide:

- Shariah-compliance screening
- Stock return classification
- Stock risk classification
- Portfolio optimization
- Backtesting
- Model explanations

## Technology Stack

- Python
- FastAPI
- pandas and NumPy
- scikit-learn
- SciPy
- pytest

## Requirements

- Python 3.11 or 3.12
- Git

## Setup

Clone the repository:

```bash
git clone https://github.com/frager098/HalalifyAI.git
cd HalalifyAI
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Run the tests:

```bash
python -m pytest
```

Start the API:

```bash
python -m uvicorn src.api.main:app --reload --port 8000
```

Open:

- Health check: `http://127.0.0.1:8000/health`
- API documentation: `http://127.0.0.1:8000/docs`

## Branches

- `main`: stable, demonstrated code
- `develop`: integration branch
- `feature/*`: individual tasks

## Security

Never commit:

- `.env`
- API keys
- Database credentials
- Large datasets
- Trained model files


## Prepare research data with one command

Install the calendar dependencies once with `pip install -r requirements-cleaning.txt`.
From the project folder, run:

```bash
python -m src.data.pipeline
```

This cleans and validates the registered audited price snapshot, builds the
existing 16-feature research dataset, and independently checks its future
targets and chronological splits. It runs offline, preserves the input and
earlier runs, and prints the dataset and report locations. It reuses the earlier
source audit; it does not download data, change screening rules or train models.

The local input is `data/interim/prices/price_repair_20261020/audited_prices.csv`.
Large data stays outside Git, so teammates need the matching data package as well
as the code. `configs/data_pipeline.json` records its exact checksum. Use
`python -m src.data.pipeline --plan` to preview the steps without writing files.

`src/data` has **10 main Python files**, with two investigation tools under
`src/data/research/`. See [the file map and individual commands](docs/data_workflow.md).

## Historical screening implementation — 20 October 2026

The current screening implementation and source review are documented in [screening_methodology.md](docs/screening_methodology.md). The executed retained-data screen covers all 50 stocks as of **31 December 2025**: **0 complete evidenced research passes, 21 initial-filter failures and 29 requiring review**. These are not current-market or official Yasaar verdicts.

Read [the simple result explanation](docs/screening_results_20261020.md) or [all 50 result rows](reports/screening/ftse_yasaar_2025/results.md). Rule code is in `src/screening/`; versioned limits and the exact cohort are in `configs/`. Install `requirements-screening.txt` after the main requirements to reproduce. The source ZIP and candidate datasets stay local and are shared separately.

The user explicitly requested this task directly on existing `develop`; no additional branch or merge was created. The latest follow-up repairs the Colab price-input checks and restores its missing feature/target imports. The older teammate modeling CSV and cleaning notebook remain preserved. One existing calendar-range operation was made compatible with pandas 3 so the repository's cleaning-calendar test also passes.

Follow-up recovery downloaded SEC CompanyFacts for all 50 and re-examined original notes. New source-backed failures are AAPL, NVDA and LOW. Read [what was recovered and what remains missing](docs/screening_field_recovery_20261020.md). Large immutable API/note snapshots are supplied separately, never committed; selected recovered figures and all 50 results are in the reports.

The latest source review also recovered four annual interest-income entries and Union Pacific's separate finance-lease liability. The new price research dataset contains 118,643 eligible rows for 50 companies, with SPY as a separate benchmark. All retained targets were independently checked; no new training accuracy is claimed. Use the source-checked `audited_prices.csv` with the repaired notebook rather than the older table's unverified review flags.

Latest source search, actual price rebuild and V5 screening findings: [data_completion_20261020.md](docs/data_completion_20261020.md). Earlier V3/V4 execution notes are historical.

The latest V6 [gap investigation](docs/screening_gap_resolution_20261020.md) clears 52 individual financial tests with source-backed maximum amounts and establishes GE's insurance business failure. This supersedes V5 screening counts. All 81 software tests pass; these are software tests, not passing stocks. Business/income gaps remain for 29 companies. The exact [data request](reports/screening/ftse_yasaar_2025/data_request.csv) and a prepared specialist enquiry (form delivery unconfirmed) are ready; no historical provider access or purchase is claimed.
