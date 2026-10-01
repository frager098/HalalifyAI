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


## Data collection and preparation

Follow [the reconciled experiment](docs/experiment_design.md), [the dictionary](docs/data_dictionary.md) and [the simple preparation guide](docs/data_reconciliation.md). The current amendment retains 50 companies plus separate SPY, uses versioned Alpaca SIP snapshots with separate price bases, and keeps intermediate financial evidence outside model-ready storage. Screening decisions remain subject to domain review. Run `python -m pytest` before submitting a feature-branch PR into develop.
