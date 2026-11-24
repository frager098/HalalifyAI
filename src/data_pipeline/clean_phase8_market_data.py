"""Clean and accept the reserved Phase 8 market snapshot without outcomes.

Student-run command:
    python -m src.data_pipeline.clean_phase8_market_data

The output is separate from Phase 3-7 data. This module never creates labels,
future returns, future volatility, model predictions, or evaluation metrics.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data_pipeline.clean_source_data import (
    PRICE_KEYS,
    PRICE_NUMERIC,
    calendar_sessions,
    clean_loop,
    coverage_report,
    price_pass,
    reconcile_raw,
)


DEFAULT_CONFIG = "configs/phase8_cleaning_v1.json"
STRUCTURAL_COLUMNS = ["open", "high", "low", "close", "volume"]
OVERLAP_COLUMNS = [*STRUCTURAL_COLUMNS, "adjusted_close"]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "input_snapshot",
        "input_normalized_sha256",
        "previous_cleaned_csv",
        "previous_cleaned_sha256",
        "output_directory",
        "collection_period",
        "overlap_period",
        "evaluation_period",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Missing config fields: {sorted(missing)}")
    collection = config["collection_period"]
    overlap = config["overlap_period"]
    evaluation = config["evaluation_period"]
    if not (
        collection["start"] <= overlap["start"] <= overlap["end"]
        < evaluation["start"] <= evaluation["end"] < collection["end"]
    ):
        raise ValueError("Overlap and evaluation dates are not properly separated")
    return config


def verify_raw_snapshot(snapshot: Path, config: dict[str, Any]) -> tuple[dict, dict]:
    metadata = json.loads((snapshot / "metadata.json").read_text(encoding="utf-8"))
    coverage = json.loads(
        (snapshot / "coverage_validation.json").read_text(encoding="utf-8")
    )
    if metadata.get("status") != "coverage_passed" or not coverage.get("passed"):
        raise ValueError("Raw Phase 8 coverage did not pass")
    if metadata.get("outcomes_inspected") or coverage.get("outcomes_inspected"):
        raise ValueError("Raw metadata says reserved outcomes were inspected")
    normalized = snapshot / metadata["normalized_csv"]
    actual = digest(normalized)
    if actual != metadata.get("normalized_sha256") or actual != config["input_normalized_sha256"]:
        raise ValueError("Normalized raw Phase 8 checksum mismatch")
    for page in metadata.get("pages", []):
        if digest(snapshot / page["file"]) != page["sha256"]:
            raise ValueError(f"Raw page checksum mismatch: {page['file']}")
    if not metadata.get("pages"):
        raise ValueError("Raw Phase 8 metadata contains no pages")
    return metadata, coverage


def compare_overlap(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    *,
    start: str,
    end: str,
    rtol: float,
    atol: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ordered_columns = PRICE_KEYS + OVERLAP_COLUMNS
    required = set(ordered_columns)
    for name, frame in (("previous", previous), ("current", current)):
        if not required.issubset(frame.columns):
            raise ValueError(f"{name} overlap input is missing {sorted(required - set(frame.columns))}")
    old = previous.loc[
        previous["session_date"].between(start, end), ordered_columns
    ].copy()
    new = current.loc[
        current["session_date"].between(start, end), ordered_columns
    ].copy()
    merged = old.merge(
        new,
        on=PRICE_KEYS,
        how="outer",
        suffixes=("_previous", "_phase8"),
        indicator=True,
        validate="one_to_one",
    ).sort_values(PRICE_KEYS, kind="stable")
    keys_match = bool(merged["_merge"].eq("both").all())
    if not keys_match:
        summary = {
            "keys_match": False,
            "previous_only": int(merged["_merge"].eq("left_only").sum()),
            "phase8_only": int(merged["_merge"].eq("right_only").sum()),
            "accepted": False,
            "classification": "overlap_key_mismatch",
        }
        return merged, summary

    column_summary: dict[str, Any] = {}
    for column in OVERLAP_COLUMNS:
        old_values = merged[f"{column}_previous"].to_numpy(dtype=float)
        new_values = merged[f"{column}_phase8"].to_numpy(dtype=float)
        equal = np.isclose(old_values, new_values, rtol=rtol, atol=atol, equal_nan=False)
        absolute = np.abs(new_values - old_values)
        relative = absolute / np.maximum(np.abs(old_values), atol)
        merged[f"{column}_changed"] = ~equal
        merged[f"{column}_absolute_difference"] = absolute
        column_summary[column] = {
            "changed_rows": int((~equal).sum()),
            "max_absolute_difference": float(absolute.max(initial=0.0)),
            "max_relative_difference": float(relative.max(initial=0.0)),
        }

    structural_changes = sum(column_summary[c]["changed_rows"] for c in STRUCTURAL_COLUMNS)
    adjusted_changes = column_summary["adjusted_close"]["changed_rows"]
    affected = []
    changed = merged.loc[merged["adjusted_close_changed"]].copy()
    if not changed.empty:
        changed["adjusted_close_ratio"] = (
            changed["adjusted_close_phase8"] / changed["adjusted_close_previous"]
        )
        for ticker, block in changed.groupby("ticker", sort=True):
            affected.append(
                {
                    "ticker": ticker,
                    "changed_rows": int(len(block)),
                    "first_changed": block["session_date"].min(),
                    "last_changed": block["session_date"].max(),
                    "ratio_min": float(block["adjusted_close_ratio"].min()),
                    "ratio_max": float(block["adjusted_close_ratio"].max()),
                }
            )

    accepted = structural_changes == 0
    classification = (
        "unexplained_structural_provider_revision"
        if structural_changes
        else "all_adjusted_close_asof_drift_documented"
        if adjusted_changes
        else "exact_overlap_match"
    )
    summary = {
        "keys_match": True,
        "rows": int(len(merged)),
        "columns": column_summary,
        "structural_changed_cells": int(structural_changes),
        "adjusted_close_changed_rows": int(adjusted_changes),
        "affected_adjusted_close_tickers": affected,
        "classification": classification,
        "accepted": accepted,
        "interpretation": (
            "Split-adjusted OHLC and volume are unchanged. Later all-adjusted-close "
            "values may reflect provider as-of corporate-action updates. The drift is "
            "documented but corporate actions remain independently unverified."
            if accepted and adjusted_changes
            else "No overlap differences were found."
            if accepted
            else "Structural price or volume history changed and requires manual evidence."
        ),
    }
    return merged, summary


def add_cleaning_fields(prices: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    prices = prices.copy()
    session_number = pd.Series(np.arange(len(sessions)), index=sessions.strftime("%Y-%m-%d"))
    prices["session_number"] = prices["session_date"].map(session_number)
    consecutive = prices.groupby("ticker")["session_number"].diff().eq(1)
    prices["split_close_return"] = prices.groupby("ticker")["close"].pct_change(fill_method=None).where(consecutive)
    prices["provider_all_adjusted_return"] = prices.groupby("ticker")["adjusted_close"].pct_change(fill_method=None).where(consecutive)
    prices["adjustment_factor"] = prices["adjusted_close"] / prices["close"]
    prices["large_return_review"] = prices["provider_all_adjusted_return"].abs().gt(0.25)
    prices["zero_volume_review"] = prices["volume"].eq(0)
    prices["identity_history_verified"] = False
    prices["adjustment_verified"] = False
    prices["core_ready"] = False
    prices["data_quality_flags"] = (
        prices["data_quality_flags"].fillna("").astype("string")
        + ";identity_history_unverified;bar_availability_unverified"
    )
    prices.loc[prices["large_return_review"], "data_quality_flags"] += ";large_return_review"
    prices.loc[prices["zero_volume_review"], "data_quality_flags"] += ";zero_volume_review"
    return prices.drop(columns="session_number")


def run(config_path: Path, root: Path) -> Path:
    config = load_config(config_path)
    snapshot = root / config["input_snapshot"]
    previous_path = root / config["previous_cleaned_csv"]
    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=False)
    history: list[dict[str, Any]] = []
    try:
        metadata, raw_coverage = verify_raw_snapshot(snapshot, config)
        if digest(previous_path) != config["previous_cleaned_sha256"]:
            raise ValueError("Previous cleaned dataset checksum mismatch")
        raw_path = snapshot / metadata["normalized_csv"]
        raw = pd.read_csv(raw_path, dtype={"ticker": "string", "session_date": "string"})
        required = set(PRICE_KEYS + PRICE_NUMERIC + ["adjustment_verified", "data_quality_flags"])
        if not required.issubset(raw.columns):
            raise ValueError(f"Raw Phase 8 data is missing {sorted(required - set(raw.columns))}")
        reconcile_raw(raw, snapshot, metadata)
        raw["source_row"] = np.arange(2, len(raw) + 2)
        period = config["collection_period"]
        prices, quarantined = clean_loop(
            raw,
            lambda frame: price_pass(frame, period["start"], period["end"]),
            "phase8_prices",
            history,
            6,
        )
        quarantine_columns = [*raw.columns, "rejection_reason", "cleaning_pass"]
        quarantined.reindex(columns=quarantine_columns).to_csv(
            output / "prices_quarantine.csv", index=False
        )
        sessions, calendar_basis = calendar_sessions(
            period["start"], period["end"], prices, False
        )
        on_calendar = pd.to_datetime(prices["session_date"]).isin(sessions)
        if not on_calendar.all():
            unexpected = prices.loc[~on_calendar].copy()
            unexpected["rejection_reason"] = "not_exchange_session"
            unexpected["cleaning_pass"] = "calendar"
            unexpected.reindex(columns=quarantine_columns).to_csv(
                output / "prices_quarantine.csv", mode="a", header=False, index=False
            )
            prices = prices.loc[on_calendar].copy()
        coverage, gaps = coverage_report(prices, sessions, sorted(raw["ticker"].unique()))
        coverage.to_csv(output / "price_coverage.csv", index=False)
        gaps.to_csv(output / "missing_sessions.csv", index=False)

        evaluation = config["evaluation_period"]
        evaluation_sessions = sessions[
            (sessions >= pd.Timestamp(evaluation["start"]))
            & (sessions <= pd.Timestamp(evaluation["end"]))
        ]
        evaluation_rows = prices.loc[
            prices["session_date"].between(evaluation["start"], evaluation["end"])
            & prices["ticker"].ne("SPY")
        ]
        active = evaluation_rows.groupby("session_date")["ticker"].nunique()
        expected_session_strings = set(evaluation_sessions.strftime("%Y-%m-%d"))
        active_session_strings = set(active.index.astype(str))
        minimum_active = int(active.min()) if not active.empty else 0

        previous = pd.read_csv(
            previous_path,
            dtype={"ticker": "string", "session_date": "string"},
            usecols=PRICE_KEYS + OVERLAP_COLUMNS,
        )
        overlap = config["overlap_period"]
        overlap_rows, overlap_summary = compare_overlap(
            previous,
            prices,
            start=overlap["start"],
            end=overlap["end"],
            rtol=float(config["numeric_rtol"]),
            atol=float(config["numeric_atol"]),
        )
        overlap_rows.to_csv(output / "overlap_comparison.csv", index=False)
        write_json(output / "overlap_revision_summary.json", overlap_summary)

        prices = add_cleaning_fields(prices, sessions)
        prices.to_csv(output / "prices_clean.csv", index=False)
        prices.loc[prices["ticker"].eq("SPY")].to_csv(output / "spy_clean.csv", index=False)
        prices.loc[
            prices["large_return_review"] | prices["zero_volume_review"]
        ].to_csv(output / "price_review.csv", index=False)
        pd.DataFrame(history).to_csv(output / "cleaning_passes.csv", index=False)

        checks = {
            "raw_checksums_verified": True,
            "raw_normalized_reconciled_to_pages": True,
            "quarantined_rows": int(len(quarantined) + (~on_calendar).sum()),
            "duplicate_keys": int(prices.duplicated(PRICE_KEYS).sum()),
            "nonfinite_numeric_rows": int((~np.isfinite(prices[PRICE_NUMERIC])).any(axis=1).sum()),
            "missing_exchange_sessions": int(len(gaps)),
            "symbols": int(prices["ticker"].nunique()),
            "evaluation_sessions_expected": int(len(evaluation_sessions)),
            "evaluation_sessions_observed": int(len(active_session_strings)),
            "minimum_active_companies": minimum_active,
            "overlap_accepted": bool(overlap_summary["accepted"]),
        }
        accepted = all(
            [
                checks["quarantined_rows"] == 0,
                checks["duplicate_keys"] == 0,
                checks["nonfinite_numeric_rows"] == 0,
                checks["missing_exchange_sessions"] == 0,
                checks["symbols"] == config["expected_symbols"],
                checks["evaluation_sessions_expected"] == config["expected_evaluation_sessions"],
                expected_session_strings == active_session_strings,
                minimum_active >= config["minimum_active_companies"],
                overlap_summary["accepted"],
            ]
        )
        report = {
            "stage": "phase_8_step_8_1_cleaning_acceptance",
            "status": "accepted_with_documented_adjustment_drift" if accepted else "rejected",
            "accepted": accepted,
            "outcomes_inspected": False,
            "labels_created": False,
            "calendar_basis": calendar_basis,
            "input_snapshot": config["input_snapshot"],
            "input_normalized_sha256": metadata["normalized_sha256"],
            "previous_cleaned_sha256": config["previous_cleaned_sha256"],
            "checks": checks,
            "raw_coverage": {
                "passed": raw_coverage["passed"],
                "latest_observed_session": raw_coverage["latest_observed_session"],
            },
            "overlap_classification": overlap_summary["classification"],
            "limitations": [
                "Corporate-action magnitudes remain independently unverified.",
                "All-adjusted close is provider as-of data and changed for some overlap rows.",
                "The fixed current 50-stock universe retains survivorship and selection bias.",
                "Bar availability timestamps are unavailable.",
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(output / "acceptance_report.json", report)
        if not accepted:
            raise ValueError("Phase 8 cleaned snapshot failed one or more acceptance gates")

        outputs = {
            path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
            for path in sorted(output.iterdir())
            if path.is_file()
        }
        write_json(output / "output_manifest.json", outputs)
        freeze = {
            "stage": "phase_8_step_8_1_accepted_clean_snapshot",
            "status": "frozen_for_phase_8_contract",
            "outcomes_inspected": False,
            "labels_created": False,
            "cleaned_csv": "prices_clean.csv",
            "cleaned_csv_sha256": outputs["prices_clean.csv"]["sha256"],
            "acceptance_report_sha256": outputs["acceptance_report.json"]["sha256"],
            "overlap_summary_sha256": outputs["overlap_revision_summary.json"]["sha256"],
            "input_snapshot": config["input_snapshot"],
            "input_normalized_sha256": metadata["normalized_sha256"],
            "cleaning_config": config_path.relative_to(root).as_posix(),
            "cleaning_config_sha256": digest(config_path),
        }
        write_json(output / "accepted_snapshot.json", freeze)
        return output
    except Exception as exc:
        write_json(
            output / "FAILED.json",
            {"type": type(exc).__name__, "error": str(exc), "outcomes_inspected": False},
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = run((root / args.config).resolve(), root)
    print(f"Accepted Phase 8 cleaned snapshot written to {output}")


if __name__ == "__main__":
    main()
