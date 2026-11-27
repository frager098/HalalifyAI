"""Check checksums and 50-company SEC evidence completeness.

Run: python -m src.data_pipeline.validate_sec_point_in_time_snapshot <snapshot-folder>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    snapshot_dir = Path(snapshot_dir)
    metadata_path = snapshot_dir / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError("Snapshot metadata.json is missing")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    tickers = metadata.get("requested_tickers", [])
    if metadata.get("schema_version") != 1 or len(tickers) != 50 or len(set(tickers)) != 50:
        raise ValueError("Snapshot has an invalid 50-stock universe declaration")

    evidence = {ticker: set() for ticker in tickers}
    ciks = {ticker: set() for ticker in tickers}
    checksum_failures = []
    for entry in metadata.get("files", []):
        name = entry.get("file")
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Manifest contains an unsafe file path")
        path = snapshot_dir / name
        if not path.is_file() or sha256(path) != entry.get("sha256"):
            checksum_failures.append(name)
            continue
        ticker = entry.get("ticker")
        if ticker in evidence:
            evidence[ticker].add(str(entry.get("kind")))
            ciks[ticker].add(str(entry.get("cik", "")).zfill(10))

    missing = {ticker: sorted({"companyfacts", "submissions"} - kinds)
               for ticker, kinds in evidence.items()
               if not {"companyfacts", "submissions"}.issubset(kinds)}
    inconsistent_ciks = sorted(ticker for ticker, values in ciks.items() if len(values) > 1)
    passed = (metadata.get("status") == "complete" and not metadata.get("failed")
              and not checksum_failures and not missing and not inconsistent_ciks)
    return {
        "snapshot": snapshot_dir.name, "status": "passed" if passed else "failed",
        "requested_tickers": len(tickers), "manifest_files": len(metadata.get("files", [])),
        "checksum_failures": checksum_failures,
        "tickers_missing_companyfacts_or_submissions": missing,
        "tickers_with_inconsistent_ciks": inconsistent_ciks,
        "historical_availability_rule": metadata.get("availability_rule"),
        "candidate_concepts_only": metadata.get("approved_candidate_concepts"),
        "not_model_approved": metadata.get("not_approved_for_model_features"),
        "limitations": metadata.get("important_limitations", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path)
    args = parser.parse_args()
    report = validate_snapshot(args.snapshot_dir)
    report_path = Path(args.snapshot_dir) / "validation_report.json"
    if report_path.exists():
        raise FileExistsError(f"Refusing to overwrite report: {report_path}")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved validation report: {report_path}")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
