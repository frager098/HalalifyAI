# HalalifyAI

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


## Screening implementation — 20 October 2026

The current screening implementation and source review are documented in [screening_methodology.md](docs/screening_methodology.md). The executed retained-data screen covers all 50 stocks as of **31 December 2025**: **0 complete evidenced research passes, 19 initial-filter failures and 31 requiring review**. These are not current-market or official Yasaar verdicts.

Read [the simple result explanation](docs/screening_results_20261020.md) or [all 50 result rows](reports/screening/ftse_yasaar_2025/results.md). Rule code is in `src/screening/`; versioned limits and the exact cohort are in `configs/`. Install `requirements-screening.txt` after the main requirements to reproduce. The source ZIP and candidate datasets stay local and are shared separately.

The user explicitly requested this task directly on existing `develop`; no additional branch or merge was created. Prediction notebooks and model data were retained. One existing calendar-range operation was made compatible with pandas 3 so the repository's cleaning-calendar test also passes.

Follow-up recovery downloaded SEC CompanyFacts for all 50 and re-examined original notes. New source-backed failures are AAPL, NVDA and LOW. Read [what was recovered and what remains missing](docs/screening_field_recovery_20261020.md). Large immutable API/note snapshots are supplied separately, never committed; selected recovered figures and all 50 results are in the reports.
