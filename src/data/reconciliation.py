"""Shared definitions for the data-reconciliation task; no model or screening rules."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

COMPANY_SYMBOLS = 'AAPL MSFT NVDA AMD AVGO ORCL ADBE CRM CSCO INTC GOOGL META NFLX AMZN TSLA HD LOW NKE SBUX MCD COST WMT JNJ LLY ABBV MRK TMO ABT DHR CAT DE HON UPS UNP GE XOM CVX COP SLB JPM BAC GS MS V MA PG KO PEP LIN NEE'.split()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
