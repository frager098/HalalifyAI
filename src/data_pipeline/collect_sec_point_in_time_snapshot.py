"""Create a dated SEC evidence snapshot without overwriting older raw data.

Run from the project folder:
    $env:SEC_USER_AGENT = "HalalifyAI FYP your-email@example.com"
    python -m src.data_pipeline.collect_sec_point_in_time_snapshot
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "sec_snapshot_v1.json"
RAW_ROOT = ROOT / "data" / "raw" / "sec_snapshots"
TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
DATA_URL = "https://data.sec.gov"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    tickers = config.get("tickers", [])
    if len(tickers) != 50 or len(set(tickers)) != 50:
        raise ValueError("SEC snapshot configuration must declare exactly 50 unique tickers")
    return config


def require_user_agent() -> str:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent or "@" not in user_agent:
        raise ValueError(
            "Set SEC_USER_AGENT first, for example: "
            '$env:SEC_USER_AGENT = "HalalifyAI FYP your-email@example.com"'
        )
    return user_agent


def fetch_bytes(url: str, user_agent: str, delay_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    try:
        with urlopen(request, timeout=90) as response:
            payload = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"SEC returned HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach SEC for {url}: {exc.reason}") from exc
    if not payload:
        raise RuntimeError(f"SEC returned an empty response for {url}")
    time.sleep(delay_seconds)
    return payload


def parse_json(payload: bytes, source_url: str) -> dict[str, Any]:
    try:
        return json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"SEC response was not valid JSON: {source_url}") from exc


def ticker_mapping(payload: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in payload.values():
        ticker = str(item.get("ticker", "")).upper()
        cik = str(item.get("cik_str", "")).zfill(10)
        if ticker and cik.isdigit():
            output[ticker] = cik
    return output


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite raw evidence: {path}")
    path.write_bytes(data)


def manifest_entry(root: Path, name: str, kind: str, ticker: str | None,
                   cik: str | None, source_url: str) -> dict[str, Any]:
    path = root / name
    return {
        "file": name.replace("\\", "/"), "kind": kind, "ticker": ticker,
        "cik": cik, "url": source_url, "sha256": sha256(path), "bytes": path.stat().st_size,
    }


def collect_snapshot(output_root: Path | None = None, config_path: Path = CONFIG,
                     user_agent: str | None = None) -> Path:
    """Download all configured evidence into one new immutable local folder."""
    config = load_config(config_path)
    user_agent = user_agent or require_user_agent()
    output_root = Path(output_root or RAW_ROOT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = output_root / stamp
    staging = output_root / f".{stamp}.staging"
    if final.exists() or staging.exists():
        raise FileExistsError(f"Snapshot directory already exists: {final}")
    staging.mkdir(parents=True, exist_ok=False)
    delay = float(config["request_delay_seconds"])
    files: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    try:
        mapping_bytes = fetch_bytes(TICKER_URL, user_agent, delay)
        write_new(staging / "company_tickers.json", mapping_bytes)
        mapping = ticker_mapping(parse_json(mapping_bytes, TICKER_URL))
        files.append(manifest_entry(staging, "company_tickers.json", "ticker_mapping", None, None, TICKER_URL))

        for ticker in config["tickers"]:
            cik = mapping.get(ticker)
            if not cik:
                failures.append({"ticker": ticker, "reason": "not in SEC ticker mapping"})
                continue
            facts_url = f"{DATA_URL}/api/xbrl/companyfacts/CIK{cik}.json"
            submissions_url = f"{DATA_URL}/submissions/CIK{cik}.json"
            try:
                facts_bytes = fetch_bytes(facts_url, user_agent, delay)
                submissions_bytes = fetch_bytes(submissions_url, user_agent, delay)
                facts = parse_json(facts_bytes, facts_url)
                submissions = parse_json(submissions_bytes, submissions_url)
                if str(facts.get("cik", "")).zfill(10) != cik:
                    raise RuntimeError("Company Facts CIK disagrees with ticker mapping")
                if str(submissions.get("cik", "")).zfill(10) != cik:
                    raise RuntimeError("Submissions CIK disagrees with ticker mapping")
                facts_name = f"{ticker}_companyfacts.json"
                submissions_name = f"{ticker}_submissions.json"
                write_new(staging / facts_name, facts_bytes)
                write_new(staging / submissions_name, submissions_bytes)
                files.append(manifest_entry(staging, facts_name, "companyfacts", ticker, cik, facts_url))
                files.append(manifest_entry(staging, submissions_name, "submissions", ticker, cik, submissions_url))
                for history in submissions.get("filings", {}).get("files", []):
                    history_name = str(history.get("name", ""))
                    if not history_name or "/" in history_name or "\\" in history_name:
                        raise RuntimeError("Invalid SEC historical-submissions filename")
                    history_url = f"{DATA_URL}/submissions/{history_name}"
                    history_bytes = fetch_bytes(history_url, user_agent, delay)
                    history_data = parse_json(history_bytes, history_url)
                    if str(history_data.get("cik", cik)).zfill(10) != cik:
                        raise RuntimeError(f"Historical submissions CIK mismatch: {history_name}")
                    stored_name = f"submissions_history/{ticker}_{history_name}"
                    write_new(staging / stored_name, history_bytes)
                    files.append(manifest_entry(staging, stored_name, "submissions_history", ticker, cik, history_url))
            except Exception as exc:
                failures.append({"ticker": ticker, "reason": str(exc)})

        metadata = {
            "schema_version": 1, "snapshot_version": config["snapshot_version"],
            "provider": "SEC EDGAR", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": config["purpose"], "availability_rule": config["availability_rule"],
            "approved_candidate_concepts": config["approved_candidate_concepts"],
            "not_approved_for_model_features": config["not_approved_for_model_features"],
            "requested_tickers": config["tickers"], "files": files, "failed": failures,
            "status": "complete" if not failures else "incomplete",
            "important_limitations": [
                "Company Facts is a current SEC API response. Check accession and filing date before use.",
                "The snapshot does not itself approve debt, revenue, receivables, net income, market capitalization, or a Shariah result.",
                "A fact is usable only after its filing date under the stated availability rule."
            ]
        }
        (staging / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if failures:
            raise RuntimeError(f"Snapshot incomplete: {len(failures)} ticker failure(s). Review {staging}.")
        staging.rename(final)
        return final
    except Exception:
        # Keep evidence already received for inspection; never silently delete raw files.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=RAW_ROOT)
    args = parser.parse_args()
    snapshot = collect_snapshot(output_root=args.output_root)
    print(f"SEC snapshot complete: {snapshot}")
    print("Next: validate this snapshot before building any model feature panel.")


if __name__ == "__main__":
    main()
