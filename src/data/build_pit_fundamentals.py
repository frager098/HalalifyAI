"""Audit SEC concepts and build a conservative research-only as-of panel.

Run: python -m src.data.build_pit_fundamentals
Only Assets and unrestricted cash/equivalents are candidates for features.
Debt and revenue are audited but not combined without semantic review.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.audit_model_prices import MODEL, ROOT, sha256


SEC = ROOT / "data/raw/sec_snapshots/20261009T110657727507Z"
PRICE = ROOT / "data/raw/alpaca/alpaca_sip_20261009T110617242394Z"
FEATURE_CONCEPTS = {"assets_usd": "Assets", "cash_usd": "CashAndCashEquivalentsAtCarryingValue"}
REVIEW_CONCEPTS = {
    "debt": ["LongTermDebtCurrent", "LongTermDebtNoncurrent",
             "LongTermDebtAndFinanceLeaseObligationsCurrent",
             "LongTermDebtAndFinanceLeaseObligationsNoncurrent"],
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "cash_alternative": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "receivables": ["AccountsReceivableNetCurrent"],
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_snapshot(directory, manifest, items, filename_key="file"):
    checks = []
    for item in items:
        name = item[filename_key]
        actual = sha256(directory / name)
        checks.append({"file": name, "ticker": item.get("ticker"),
                       "expected_sha256": item["sha256"], "actual_sha256": actual,
                       "matches": actual == item["sha256"]})
    return pd.DataFrame(checks)


def extract_instant_facts(payload, ticker, field, concept):
    rows = []
    observations = payload.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {}).get("USD", [])
    for source_row, fact in enumerate(observations, start=1):
        if fact.get("form") not in ("10-K", "10-Q") or fact.get("start") is not None:
            continue
        try:
            end = pd.Timestamp(fact["end"])
            filed = pd.Timestamp(fact["filed"])
            value = float(fact["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if pd.isna(end) or pd.isna(filed) or end > filed or not np.isfinite(value):
            continue
        if (field == "assets_usd" and value <= 0) or (field == "cash_usd" and value < 0):
            continue
        accession = fact.get("accn")
        if not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            continue
        # A date-only SEC filing date is not proof of intraday availability.
        # Starting the next calendar day makes the first tradable date conservative.
        rows.append({"ticker": ticker, "field": field, "concept": concept,
                     "period_end": end.strftime("%Y-%m-%d"),
                     "filing_date": filed.strftime("%Y-%m-%d"),
                     "available_date": (filed + timedelta(days=1)).strftime("%Y-%m-%d"),
                     "accession_number": accession, "value_usd": value,
                     "cik": str(payload.get("cik", "")).zfill(10),
                     "source_file": f"{ticker}_companyfacts.json",
                     "source_observation": source_row, "unit": "USD", "form": fact["form"]})
    return rows


def resolve_fact_versions(facts):
    """Keep one current-period fact per accession; quarantine conflicts."""
    if facts.empty:
        return facts.copy(), facts.copy()
    keys = ["ticker", "field", "accession_number", "period_end", "filing_date"]
    work = facts.drop_duplicates(keys + ["value_usd"]).copy()
    conflicting = work.groupby(keys).value_usd.transform("nunique").gt(1)
    quarantine = work[conflicting].copy()
    work = work[~conflicting].copy()
    # One filing can repeat older comparative balance sheets. Use its latest
    # balance-sheet date, not an older comparative with the same filed date.
    latest_end = work.groupby(["ticker", "field", "accession_number"]).period_end.transform("max")
    work = work[work.period_end.eq(latest_end)].copy()
    same_day = ["ticker", "field", "available_date", "period_end"]
    disputed = work.groupby(same_day).value_usd.transform("nunique").gt(1)
    quarantine = pd.concat([quarantine, work[disputed]], ignore_index=True)
    return work[~disputed].copy(), quarantine


def asof_field(sessions, facts, field):
    """For each ticker/date select latest period, then latest known filing."""
    out = []
    for ticker, block in sessions.groupby("ticker", sort=False):
        observations = facts[(facts.ticker == ticker) & (facts.field == field)].copy()
        if observations.empty:
            missing = block.copy()
            for name in ("value_usd", "period_end", "filing_date", "available_date", "accession_number"):
                missing[name] = np.nan
            out.append(missing)
            continue
        observations = observations.sort_values(
            ["available_date", "period_end", "filing_date", "accession_number"])
        newest_period = observations.period_end.cummax()
        observations = observations[observations.period_end.eq(newest_period)]
        # Same-day same-period conflicts were quarantined above. Repeated equal
        # facts are equivalent numerically; keep a deterministic accession.
        observations = observations.drop_duplicates("available_date", keep="last")
        observations["available_key"] = pd.to_datetime(observations.available_date)
        dated_block = block.copy()
        dated_block["session_key"] = pd.to_datetime(dated_block.session_date)
        selected = pd.merge_asof(
            dated_block.sort_values("session_key"), observations,
            left_on="session_key", right_on="available_key", direction="backward",
            suffixes=("", "_fact"),
        )
        out.append(selected)
    return pd.concat(out, ignore_index=True).sort_values("row_id").reset_index(drop=True)


def build_panel(model, facts):
    sessions = model[["ticker", "session_date"]].copy()
    sessions["row_id"] = np.arange(len(sessions))
    assets = asof_field(sessions, facts, "assets_usd")
    cash = asof_field(sessions, facts, "cash_usd")
    panel = sessions.copy()
    for name, selected in (("assets", assets), ("cash", cash)):
        for source, target in (("value_usd", f"{name}_usd"),
                               ("period_end", f"{name}_period_end"),
                               ("filing_date", f"{name}_filing_date"),
                               ("available_date", f"{name}_available_date"),
                               ("accession_number", f"{name}_accession")):
            panel[target] = selected[source].to_numpy()
    same_statement = (panel.assets_period_end.eq(panel.cash_period_end)
                      & panel.assets_accession.eq(panel.cash_accession))
    ratio = (panel.cash_usd / panel.assets_usd).where(same_statement)
    panel["cash_to_assets"] = ratio.where(ratio.between(0, 1))
    panel["ratio_source_same_filing"] = same_statement.fillna(False)
    panel["historical_identity_verified"] = False
    panel["sec_snapshot_as_filed_vintage_verified"] = False
    for name in ("assets", "cash"):
        used = panel[f"{name}_available_date"].notna()
        if not panel.loc[used, f"{name}_available_date"].le(panel.loc[used, "session_date"]).all():
            raise AssertionError(f"Future {name} filing leaked into panel")
    if panel.duplicated(["ticker", "session_date"]).any() or len(panel) != len(model):
        raise AssertionError("Panel keys differ from model")
    return panel.drop(columns="row_id")


def run(model_path=MODEL, sec_dir=SEC, price_dir=PRICE, evidence=None):
    sec_meta = load_json(sec_dir / "metadata.json")
    price_meta = load_json(price_dir / "metadata.json")
    sec_checks = verify_snapshot(sec_dir, sec_meta, sec_meta["files"])
    price_checks = verify_snapshot(price_dir, price_meta, price_meta["pages"])
    if sha256(sec_dir / "company_tickers.json") != sec_meta["ticker_mapping_sha256"]:
        raise ValueError("SEC ticker mapping checksum mismatch")
    model_meta = load_json(Path(model_path).with_name("targets_metadata.json"))
    if sha256(model_path) != model_meta["output_sha256"]:
        raise ValueError("Model input checksum mismatch")
    model = pd.read_csv(model_path, usecols=["ticker", "session_date"])
    bad_sec = set(sec_checks.loc[~sec_checks.matches, "ticker"])
    files = {item["ticker"]: item for item in sec_meta["files"] if item["kind"] == "companyfacts"}
    forms = {item["ticker"]: item for item in sec_meta["files"] if item["kind"] == "submissions"}
    rows, coverage, fact_rows = [], [], []
    for ticker in sorted(model.ticker.unique()):
        if ticker in bad_sec or ticker not in files or ticker not in forms:
            coverage.append({"ticker": ticker, "source_verified": False, "reason": "SEC snapshot checksum mismatch or missing file"})
            for group, concepts in REVIEW_CONCEPTS.items():
                for concept in concepts:
                    fact_rows.append({"ticker": ticker, "review_group": group, "concept": concept,
                                      "disposition": "excluded_source_integrity", "approved_feature": False})
            continue
        facts = load_json(sec_dir / files[ticker]["file"])
        sub = load_json(sec_dir / forms[ticker]["file"])
        if str(facts["cik"]).zfill(10) != str(sub["cik"]).zfill(10):
            raise ValueError(f"{ticker}: CIK mismatch")
        for field, concept in FEATURE_CONCEPTS.items():
            rows.extend(extract_instant_facts(facts, ticker, field, concept))
        gaap = facts.get("facts", {}).get("us-gaap", {})
        for group, concepts in REVIEW_CONCEPTS.items():
            for concept in concepts:
                units = gaap.get(concept, {}).get("units", {})
                obs = [x for x in units.get("USD", []) if x.get("form") in ("10-Q", "10-K")]
                fact_rows.append({"ticker": ticker, "review_group": group, "concept": concept,
                                  "usd_10k_10q_observations": len(obs),
                                  "duration_observations": sum(x.get("start") is not None for x in obs),
                                  "units_present": ",".join(sorted(units)),
                                  "amended_usd_observations": sum(x.get("form") in ("10-K/A", "10-Q/A") for x in units.get("USD", [])),
                                  "disposition": "semantic_review_required" if obs else "missing_candidate_concept",
                                  "approved_feature": False,
                                  "reason": {"debt": "Alternative components may overlap; no automatic sum",
                                             "revenue": "Quarter/YTD/year durations need fiscal reconciliation",
                                             "cash_alternative": "Includes restricted cash; not equivalent to unrestricted cash",
                                             "receivables": "Issuer-specific concept coverage and net/gross meaning need review"}[group]})
        coverage.append({"ticker": ticker, "source_verified": True, "reason": "verified current SEC snapshot; historical identity still open"})
    raw_facts = pd.DataFrame(rows)
    resolved, quarantine = resolve_fact_versions(raw_facts)
    if evidence is not None:
        evidence["selected_facts"] = resolved
        evidence["candidate_observations"] = len(raw_facts)
        evidence["changed_values_across_filings"] = int(raw_facts.groupby(
            ["ticker", "field", "period_end"]).value_usd.nunique().gt(1).sum())
    panel = build_panel(model, resolved)
    for ticker in bad_sec:
        if panel.loc[panel.ticker.eq(ticker), ["assets_usd", "cash_usd"]].notna().any().any():
            raise AssertionError(f"Unverified SEC source entered panel: {ticker}")
    summary = {
        "model_sha256": model_meta["output_sha256"],
        "sec_snapshot": sec_dir.name, "sec_files": len(sec_checks),
        "sec_checksum_mismatches": sec_checks.loc[~sec_checks.matches, "file"].tolist(),
        "alpaca_raw_page_checksum_mismatches": price_checks.loc[~price_checks.matches, "file"].tolist(),
        "eligible_sec_tickers": int(pd.DataFrame(coverage).source_verified.sum()),
        "excluded_sec_tickers": sorted(bad_sec),
        "selected_instant_fact_rows": len(resolved), "conflicting_fact_rows": len(quarantine),
        "panel_rows": len(panel),
        "rows_with_assets": int(panel.assets_usd.notna().sum()),
        "rows_with_cash": int(panel.cash_usd.notna().sum()),
        "rows_with_same_filing_cash_to_assets": int(panel.cash_to_assets.notna().sum()),
        "ready_for_model_training": False,
        "reason": "SEC source exclusions and historical identity/vintage checks remain unresolved; inspect checksum lists separately.",
    }
    return summary, sec_checks, price_checks, pd.DataFrame(coverage), pd.DataFrame(fact_rows), quarantine, panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary, sec_checks, price_checks, coverage, concepts, quarantine, panel = run()
    out = args.output_dir or ROOT / "reports/generated" / datetime.now(timezone.utc).strftime("pit_fundamentals_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    for name, frame in (("sec_source_checks", sec_checks), ("price_source_checks", price_checks),
                        ("ticker_coverage", coverage), ("concept_review", concepts),
                        ("fact_conflicts", quarantine), ("fundamental_panel", panel)):
        frame.to_csv(out / f"{name}.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
