"""Download a separate, versioned SPY reference snapshot. Run from repo root."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = "https://data.alpaca.markets/v2/stocks/bars"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / "src").is_dir():
        raise ValueError("Run from the HalalifyAI root folder, or pass --repo PATH.")
    load_dotenv(repo / ".env")
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise ValueError("Set ALPACA_API_KEY and ALPACA_SECRET_KEY in your local .env.")

    # Explicit US-local bounds include every session dated 2015 through 2025.
    params = {
        "symbols": "SPY", "timeframe": "1Day",
        "start": "2015-01-01T00:00:00-05:00",
        "end": "2025-12-31T23:59:59-05:00",
        "feed": "sip", "adjustment": "all", "currency": "USD",
        "asof": "2025-12-31", "limit": 10000, "sort": "asc",
    }
    initial_params = params.copy()
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ")
    folder = repo / "data" / "raw" / "benchmarks" / "SPY" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {
        "status": "started", "role": "market_reference_not_company_candidate",
        "started_at_utc": started.isoformat(), "endpoint": URL,
        "request_parameters": initial_params,
        "adjustment_note": "OHLC uses adjustment=all, matching current company downloader."
        " No separate unadjusted close or action ledger is collected.",
        "pages": [],
    }
    metadata_path = folder / "metadata.json"
    rows = []
    seen_tokens = set()
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"APCA-API-KEY-ID": key,
                            "APCA-API-SECRET-KEY": secret})
    print("Downloading SPY only: SIP, 2015-2025. Company files are preserved.")
    try:
        while True:
            page_number = len(metadata["pages"]) + 1
            print(f"Downloading page {page_number}...", flush=True)
            response = session.get(URL, params=params, timeout=(15, 60))
            if response.status_code != 200:
                raise RuntimeError(f"Alpaca HTTP {response.status_code}. "
                                   "Check credentials, SIP access or request limits.")
            raw = response.content
            page_path = folder / f"page_{page_number:04d}.json"
            page_path.write_bytes(raw)
            metadata["pages"].append({
                "file": page_path.name,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            data = response.json()
            bars = data.get("bars") or {}
            if set(bars) - {"SPY"}:
                raise ValueError("Unexpected ticker returned; inspect saved response.")
            for bar in bars.get("SPY", []):
                rows.append({"timestamp": bar["t"], "ticker": "SPY",
                             "open": bar["o"], "high": bar["h"],
                             "low": bar["l"], "close": bar["c"],
                             "volume": bar["v"]})
            token = data.get("next_page_token")
            if not token:
                break
            if token in seen_tokens:
                raise ValueError("Repeated pagination token; stopping incomplete download.")
            seen_tokens.add(token)
            params["page_token"] = token
            time.sleep(0.2)

        if not rows:
            raise ValueError("No SPY bars returned. Do not treat this as a successful download.")
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df.pop("timestamp"), utc=True).dt.tz_convert(
            "America/New_York").dt.strftime("%Y-%m-%d")
        df = df[["date", "ticker", "open", "high", "low", "close", "volume"]]
        df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
        numeric = ["open", "high", "low", "close", "volume"]
        for column in numeric:
            df[column] = pd.to_numeric(df[column], errors="raise")
        if df.isna().any().any() or df.duplicated(["ticker", "date"]).any():
            raise ValueError("Missing values or duplicate sessions; raw pages retained for review.")
        if not df["date"].between("2015-01-01", "2025-12-31").all():
            raise ValueError("Unexpected session outside requested period.")
        if (df[["open", "high", "low", "close"]] <= 0).any().any() or (df.volume < 0).any():
            raise ValueError("Invalid nonpositive prices or negative volume.")
        if ((df.high < df[["open", "close", "low"]].max(axis=1)) |
                (df.low > df[["open", "close", "high"]].min(axis=1))).any():
            raise ValueError("Inconsistent daily high/low values.")
        output = folder / "alpaca_spy_historical_prices.csv"
        df.to_csv(output, index=False)
        summary = df.groupby("ticker").agg(
            rows=("date", "count"), first_date=("date", "min"),
            last_date=("date", "max")).reset_index()
        summary.to_csv(folder / "alpaca_spy_data_summary.csv", index=False)
        metadata.update(status="downloaded_basic_checks_passed", rows=len(df),
                        first_date=df.date.min(), last_date=df.date.max(),
                        csv_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                        calendar_coverage_status="not_yet_audited")
        print(summary.to_string(index=False))
        print(f"Saved to: {folder}")
        print("Basic checks passed. Full exchange-calendar coverage and adjustment validation remain.")
    except Exception as exc:
        metadata.update(status="failed", error=str(exc))
        print(f"Download failed. Available raw responses and metadata are retained in {folder}")
        raise
    finally:
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        session.close()


if __name__ == "__main__":
    main()
