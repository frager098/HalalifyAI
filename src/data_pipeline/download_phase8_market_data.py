"""Collect a separate, immutable Alpaca snapshot for Phase 8.

This module only collects bars and validates date/symbol coverage. It does not
build features or labels and deliberately has no dependency on the Phase 3-7
processed datasets.

Student-run command:
    python -m src.data_pipeline.download_phase8_market_data
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import exchange_calendars as xc


DEFAULT_CONFIG = "configs/phase8_market_data_collection_v1.json"
ENDPOINT = "https://data.alpaca.markets/v2/stocks/bars"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "evaluation_period",
        "collection_period",
        "adjustments",
        "symbols",
        "output_root",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Missing config keys: {sorted(missing)}")

    evaluation = config["evaluation_period"]
    collection = config["collection_period"]
    dates = {
        name: pd.Timestamp(value)
        for name, value in {
            "evaluation_start": evaluation["start"],
            "evaluation_end": evaluation["end"],
            "collection_start": collection["start"],
            "collection_end": collection["end"],
        }.items()
    }
    if not (
        dates["collection_start"]
        < dates["evaluation_start"]
        <= dates["evaluation_end"]
        < dates["collection_end"]
    ):
        raise ValueError("Collection dates must surround the evaluation period")
    if config["adjustments"] != ["split", "all"]:
        raise ValueError("Phase 8 requires split and all adjustment snapshots")
    symbols = config["symbols"]
    if len(symbols) != 51 or len(set(symbols)) != 51 or symbols.count("SPY") != 1:
        raise ValueError("Expected the frozen 50-stock universe plus SPY")
    return config


def _request_pages(
    *,
    session: requests.Session,
    headers: dict[str, str],
    config: dict[str, Any],
    adjustment: str,
    output: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    params: dict[str, Any] = {
        "symbols": ",".join(config["symbols"]),
        "timeframe": config["timeframe"],
        "start": f'{config["collection_period"]["start"]}T00:00:00Z',
        "end": f'{config["collection_period"]["end"]}T23:59:59Z',
        "feed": config["feed"],
        "currency": config["currency"],
        "adjustment": adjustment,
        "limit": 10000,
        "sort": "asc",
    }
    page_token: str | None = None
    pages: list[dict[str, Any]] = []
    bars: list[dict[str, Any]] = []
    page_number = 1

    while True:
        request_params = dict(params)
        if page_token:
            request_params["page_token"] = page_token
        response = session.get(ENDPOINT, headers=headers, params=request_params, timeout=90)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("bars"), dict):
            raise ValueError("Alpaca response is missing the bars object")

        page_path = output / f"{adjustment}_{page_number:04d}.json"
        if page_path.exists():
            raise FileExistsError(page_path)
        page_path.write_bytes(response.content)
        pages.append(
            {
                "file": page_path.name,
                "sha256": sha256(page_path),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        for ticker, ticker_bars in payload["bars"].items():
            for bar in ticker_bars:
                bars.append({"ticker": ticker, **bar})

        page_token = payload.get("next_page_token")
        if not page_token:
            break
        page_number += 1

    return pages, bars


def normalize_bars(
    split_bars: list[dict[str, Any]],
    all_bars: list[dict[str, Any]],
    dataset_version: str,
) -> pd.DataFrame:
    def keyed(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row["ticker"], row["t"][:10])
            if key in result:
                raise ValueError(f"Duplicate Alpaca bar: {key}")
            result[key] = row
        return result

    split = keyed(split_bars)
    adjusted = keyed(all_bars)
    if split.keys() != adjusted.keys():
        missing_all = sorted(split.keys() - adjusted.keys())[:5]
        missing_split = sorted(adjusted.keys() - split.keys())[:5]
        raise ValueError(
            "Adjustment snapshots have different keys; "
            f"missing_all={missing_all}, missing_split={missing_split}"
        )

    rows = []
    for (ticker, session_date), split_row in sorted(split.items()):
        rows.append(
            {
                "ticker": ticker,
                "session_date": session_date,
                "open": split_row["o"],
                "high": split_row["h"],
                "low": split_row["l"],
                "close": split_row["c"],
                "volume": split_row["v"],
                "adjusted_close": adjusted[(ticker, session_date)]["c"],
                "dataset_version": dataset_version,
                "instrument_id": f"US_{ticker}",
                "security_type": "etf" if ticker == "SPY" else "common_stock",
                "currency": "USD",
                "dividend_per_share": pd.NA,
                "split_ratio": pd.NA,
                "bar_available_at": pd.NA,
                "adjustment_verified": False,
                "data_quality_flags": "action_evidence_not_verified",
            }
        )
    return pd.DataFrame(rows)


def validate_coverage(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    evaluation = config["evaluation_period"]
    collection = config["collection_period"]
    dates = pd.to_datetime(frame["session_date"], format="%Y-%m-%d", errors="raise")
    work = frame.assign(_date=dates)
    if work.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate ticker/date keys in normalized snapshot")
    if set(work["ticker"]) != set(config["symbols"]):
        raise ValueError("Normalized snapshot does not contain exactly the configured symbols")

    calendar = xc.get_calendar(
        "XNYS",
        start=pd.Timestamp(collection["start"]) - pd.Timedelta(days=10),
        end=pd.Timestamp(collection["end"]) + pd.Timedelta(days=10),
    )
    expected_evaluation = calendar.sessions_in_range(
        evaluation["start"], evaluation["end"]
    ).tz_localize(None)
    after_end = calendar.sessions_in_range(
        pd.Timestamp(evaluation["end"]) + pd.Timedelta(days=1), collection["end"]
    ).tz_localize(None)
    if len(after_end) < 20:
        raise ValueError("Collection period does not contain 20 sessions after evaluation end")
    label_support_end = after_end[19]

    evaluation_rows = work.loc[
        work["_date"].between(expected_evaluation[0], expected_evaluation[-1])
    ]
    company_rows = evaluation_rows.loc[evaluation_rows["ticker"].ne("SPY")]
    active = company_rows.groupby("_date")["ticker"].nunique()
    expected_dates = set(expected_evaluation)
    observed_dates = set(active.index)
    minimum_active = int(active.min()) if not active.empty else 0
    passed = (
        expected_dates == observed_dates
        and minimum_active >= config["minimum_active_companies"]
        and work["_date"].max() >= label_support_end
    )

    symbol_coverage = {}
    for ticker, block in work.groupby("ticker", sort=True):
        symbol_coverage[ticker] = {
            "first": block["session_date"].min(),
            "last": block["session_date"].max(),
            "rows": int(len(block)),
        }
    return {
        "stage": "phase_8_step_8_1_coverage_validation",
        "outcomes_inspected": False,
        "passed": passed,
        "evaluation_start": evaluation["start"],
        "evaluation_end": evaluation["end"],
        "evaluation_sessions_expected": int(len(expected_evaluation)),
        "evaluation_sessions_observed": int(len(observed_dates)),
        "minimum_active_companies": minimum_active,
        "required_minimum_active_companies": config["minimum_active_companies"],
        "twentieth_support_session_after_evaluation": label_support_end.strftime("%Y-%m-%d"),
        "latest_observed_session": work["session_date"].max(),
        "missing_evaluation_sessions": sorted(d.strftime("%Y-%m-%d") for d in expected_dates - observed_dates),
        "symbol_coverage": symbol_coverage,
    }


def collect(config_path: Path, root: Path, session: requests.Session | None = None) -> Path:
    config = load_config(config_path)
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required for collection; install requirements-cleaning.txt"
        ) from exc
    load_dotenv(root / ".env")
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required in .env")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dataset_version = f"phase8_alpaca_sip_{timestamp}"
    output = root / config["output_root"] / dataset_version
    output.mkdir(parents=True, exist_ok=False)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    client = session or requests.Session()

    page_records: list[dict[str, Any]] = []
    collected: dict[str, list[dict[str, Any]]] = {}
    for adjustment in config["adjustments"]:
        pages, bars = _request_pages(
            session=client,
            headers=headers,
            config=config,
            adjustment=adjustment,
            output=output,
        )
        page_records.extend({"adjustment": adjustment, **page} for page in pages)
        collected[adjustment] = bars

    normalized = normalize_bars(collected["split"], collected["all"], dataset_version)
    normalized_path = output / "daily_prices.csv"
    normalized.to_csv(normalized_path, index=False)
    coverage = validate_coverage(normalized, config)
    write_json(output / "coverage_validation.json", coverage)
    metadata = {
        "dataset_version": dataset_version,
        "stage": "phase_8_market_data_collection",
        "status": "coverage_passed" if coverage["passed"] else "coverage_failed",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "config": config_path.relative_to(root).as_posix(),
        "config_sha256": sha256(config_path),
        "source_requests": {
            "endpoint": ENDPOINT,
            "feed": config["feed"],
            "timeframe": config["timeframe"],
            "collection_period": config["collection_period"],
            "adjustments": config["adjustments"],
            "symbols": config["symbols"],
        },
        "pages": page_records,
        "normalized_csv": normalized_path.name,
        "normalized_sha256": sha256(normalized_path),
        "coverage_validation": "coverage_validation.json",
        "outcomes_inspected": False,
    }
    write_json(output / "metadata.json", metadata)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = collect((root / args.config).resolve(), root)
    print(f"Phase 8 snapshot written to {output}")


if __name__ == "__main__":
    main()
