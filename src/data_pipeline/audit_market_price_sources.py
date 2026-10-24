"""Read-only internal audit of the preserved SIP modeling input.

Run: python -m src.data_pipeline.audit_market_price_sources
This checks saved provenance, coverage and review flags. It cannot certify
corporate actions or historical information availability from one snapshot.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/model_dataset.csv"
SNAPSHOT = ROOT / "data/raw/alpaca/alpaca_sip_20261009T110617242394Z/metadata.json"
INTERIM = ROOT / "data/interim/prices/alpaca_sip_20261009T110617242394Z/daily_prices.csv"


def compare_raw_pages(price_dir, metadata, interim):
    """Compare each saved page with the columns actually retained downstream.

    Equality here is internal consistency, never proof of original provider bytes.
    The all-adjusted OHLC/volume were not retained, so only its close is compared.
    """
    reference = interim.set_index(["ticker", "session_date"])
    if not reference.index.is_unique:
        raise ValueError("Duplicate interim keys")
    reference_rows = reference.to_dict(orient="index")
    summaries, differences = [], []
    seen = {"split": set(), "all": set()}
    for item in metadata["pages"]:
        name = item["file"]
        basis = name.split("_")[0]
        if basis not in seen:
            raise ValueError(f"Unknown adjustment basis: {name}")
        payload = json.loads((price_dir / name).read_text(encoding="utf-8-sig"))
        pairs = {"close": "c", "open": "o", "high": "h", "low": "l", "volume": "v"} if basis == "split" else {"adjusted_close": "c"}
        count = mismatch = duplicates = 0
        for ticker, bars in (payload.get("bars") or {}).items():
            for bar in bars:
                stamp = pd.Timestamp(bar["t"])
                if stamp.tzinfo is None:
                    raise ValueError(f"Naive bar timestamp in {name}")
                date = stamp.tz_convert("America/New_York").strftime("%Y-%m-%d")
                key = (ticker, date)
                count += 1
                duplicates += int(key in seen[basis])
                seen[basis].add(key)
                if key not in reference_rows:
                    differences.append(dict(file=name, ticker=ticker, session_date=date, column="key", reason="raw_only"))
                    mismatch += 1
                    continue
                row = reference_rows[key]
                for col, raw_col in pairs.items():
                    if not np.isclose(float(row[col]), float(bar[raw_col]), rtol=0, atol=1e-10):
                        mismatch += 1
                        differences.append(dict(file=name, ticker=ticker, session_date=date, column=col,
                                                raw_value=bar[raw_col], interim_value=row[col], reason="value_difference"))
        summaries.append(dict(file=name, basis=basis, rows=count, compared_columns=",".join(pairs),
                              differing_values_or_keys=mismatch, duplicate_keys=duplicates,
                              matches_manifest=sha256(price_dir / name) == item["sha256"],
                              interpretation="saved_values_match_only" if not mismatch and not duplicates else "review_required"))
    for basis, keys in seen.items():
        for ticker, date in sorted(set(reference.index) - keys):
            differences.append(dict(file=basis, ticker=ticker, session_date=date, column="key", reason="interim_only"))
    return pd.DataFrame(summaries), pd.DataFrame(differences, columns=[
        "file", "ticker", "session_date", "column", "raw_value", "interim_value", "reason"])


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(model_path=MODEL, snapshot_path=SNAPSHOT, interim_path=INTERIM):
    model_path, snapshot_path, interim_path = map(Path, (model_path, snapshot_path, interim_path))
    model_meta = json.loads(model_path.with_name("targets_metadata.json").read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    model_hash, interim_hash = sha256(model_path), sha256(interim_path)
    if model_hash != model_meta["output_sha256"]:
        raise ValueError("Modeling CSV differs from its saved checksum")
    if interim_hash != snapshot["normalized_sha256"]:
        raise ValueError("Interim CSV differs from the SIP snapshot manifest")

    model = pd.read_csv(model_path, low_memory=False)
    interim = pd.read_csv(interim_path, low_memory=False)
    if model.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate modeling ticker/date keys")
    if interim.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate interim ticker/date keys")
    company = interim[interim.ticker.ne("SPY")]
    columns = ["ticker", "session_date", "open", "high", "low", "close", "volume", "adjusted_close"]
    paired = model[columns].merge(company[columns], on=["ticker", "session_date"],
                                  how="outer", indicator=True, suffixes=("_model", "_interim"),
                                  validate="one_to_one")
    absent = int(paired._merge.ne("both").sum())
    unequal = 0
    both = paired._merge.eq("both")
    for column in columns[2:]:
        unequal += int((~np.isclose(paired.loc[both, f"{column}_model"],
                                   paired.loc[both, f"{column}_interim"],
                                   rtol=0, atol=1e-10)).sum())
    if absent or unequal:
        raise ValueError(f"Model/interim price mismatch: {absent} keys, {unequal} values")

    spy_dates = set(interim.loc[interim.ticker.eq("SPY"), "session_date"])
    coverage = model.groupby("ticker").agg(rows=("session_date", "size"),
                                           first_date=("session_date", "min"),
                                           last_date=("session_date", "max")).reset_index()
    # Build sets once so this audit remains fast on a large modeling table.
    ticker_dates = {ticker: set(group.session_date) for ticker, group in model.groupby("ticker")}
    coverage["missing_vs_spy_during_listing"] = coverage.apply(
        lambda row: sum(row.first_date <= date <= row.last_date and date not in ticker_dates[row.ticker]
                        for date in spy_dates), axis=1,
    )

    numeric = ["open", "high", "low", "close", "adjusted_close", "volume"]
    bad_numeric = int((~np.isfinite(model[numeric])).any(axis=1).sum())
    bad_ohlc = int((model.high < model[["open", "low", "close"]].max(axis=1)).sum()
                   + (model.low > model[["open", "high", "close"]].min(axis=1)).sum())
    flagged = model[model.large_return_review.eq(True)][
        ["ticker", "session_date", "provider_all_adjusted_return", "data_quality_flags"]
    ].copy()
    summary = {
        "snapshot_provider": snapshot["provider"],
        "snapshot_version": snapshot["dataset_version"],
        "requested_start": snapshot["requested_start"],
        "requested_end": snapshot["requested_end"],
        "snapshot_status": snapshot["status"],
        "snapshot_core_ready": snapshot["core_ready"],
        "model_sha256": model_hash,
        "interim_sha256": interim_hash,
        "model_rows": int(len(model)),
        "modeled_tickers": int(model.ticker.nunique()),
        "model_first_date": model.session_date.min(),
        "model_last_date": model.session_date.max(),
        "model_interim_price_match": True,
        "duplicate_model_keys": int(model.duplicated(["ticker", "session_date"]).sum()),
        "nonfinite_numeric_rows": bad_numeric,
        "invalid_ohlc_conditions": bad_ohlc,
        "nonpositive_price_rows": int(model[["open", "high", "low", "close", "adjusted_close"]].le(0).any(axis=1).sum()),
        "negative_volume_rows": int(model.volume.lt(0).sum()),
        "missing_vs_spy_during_listing": int(coverage.missing_vs_spy_during_listing.sum()),
        "unverified_adjustment_rows": int(model.adjustment_verified.eq(False).sum()),
        "unverified_identity_rows": int(model.identity_history_verified.eq(False).sum()),
        "missing_bar_available_at_rows": int(model.bar_available_at.isna().sum()),
        "core_not_ready_rows": int(model.core_ready.eq(False).sum()),
        "large_return_review_rows": int(len(flagged)),
        "zero_volume_review_rows": int(model.zero_volume_review.eq(True).sum()),
        "interpretation": "Internal consistency passed; provider adjustment, historical identity and bar availability remain unverified.",
    }
    return summary, coverage, flagged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary, coverage, flagged = audit()
    out = args.output_dir or ROOT / "reports/generated" / datetime.now(timezone.utc).strftime("price_audit_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    coverage.to_csv(out / "ticker_coverage.csv", index=False)
    flagged.to_csv(out / "large_moves_review.csv", index=False)
    print(json.dumps(summary, indent=2))
    print(f"Saved audit: {out}")


if __name__ == "__main__":
    main()
