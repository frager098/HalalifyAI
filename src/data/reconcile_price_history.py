"""Reconcile saved SIP price bases and document historical identity/decision timing.

Run: python -m src.data.reconcile_price_history
This is an evidence report. It never upgrades the model's readiness flags.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from src.data.audit_model_prices import MODEL, SNAPSHOT, ROOT, audit


SEC_DIR = ROOT / "data/raw/sec_snapshots/20261009T110657727507Z"

# Primary issuer announcements establish these dated identity/action events.
# They do not independently certify Alpaca's historical OHLC values.
DOCUMENTED_EVENTS = {
    ("META", "2022-06-09"): (
        "FB became META before market open; same Class A shares and CUSIP",
        "https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx",
    ),
    ("LIN", "2018-10-31"): (
        "Linde plc began NYSE trading; Praxair/Linde AG business combination",
        "https://www.linde.com/news-and-media/2018/business-combination-between-praxair-and-linde-ag-successfully-completed",
    ),
    ("GE", "2023-01-04"): (
        "GE HealthCare spin-off; GE continued trading under GE",
        "https://www.ge.com/news/press-releases/ge-completes-separation-of-ge-healthcare",
    ),
    ("GE", "2024-04-02"): (
        "GE Vernova spin-off; GE continued as GE Aerospace under GE",
        "https://www.ge.com/news/press-releases/ge-board-of-directors-approves-spin-off-of-ge-vernova-ge-vernova-and-ge-aerospace-to",
    ),
    ("DHR", "2023-10-02"): (
        "Veralto began regular-way trading after Danaher separation",
        "https://investors.danaher.com/2023-09-30-Danaher-Corporation-Completes-Separation-of-Veralto-Corporation",
    ),
    ("HON", "2025-10-30"): (
        "Solstice spin-off distribution; HON continued under HON",
        "https://investor.honeywell.com/news-releases/news-release-details/honeywell-board-directors-approves-spin-solstice-advanced",
    ),
}

# Dated public news provides context for a large move, not price verification
# and not a causal proof. COP has no sourced company event here.
MOVE_CONTEXT = {
    ("AMD", "2016-04-22"): ("Prior-session earnings release", "https://ir.amd.com/news-events/press-releases/detail/683/amd-reports-2016-first-quarter-results"),
    ("CRM", "2020-08-26"): ("Prior-session earnings release", "https://investor.salesforce.com/news/news-details/2020/Salesforce-Announces-Strong-Second-Quarter-Fiscal-2021-Results/default.aspx"),
    ("INTC", "2024-08-02"): ("Prior-session earnings release", "https://www.intc.com/news-events/press-releases/detail/1704/intel-reports-second-quarter-2024-financial-results"),
    ("META", "2022-02-03"): ("Prior-session earnings release; historical ticker FB", "https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Reports-Fourth-Quarter-and-Full-Year-2021-Results/default.aspx"),
    ("NFLX", "2022-04-20"): ("Prior-session earnings release", "https://ir.netflix.net/investor-news-and-events/financial-releases/press-release-details/2022/Netflix-Releases-First-Quarter-2022-Financial-Results/default.aspx"),
    ("NVDA", "2016-11-11"): ("Prior-session earnings release", "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2017"),
    ("ORCL", "2025-09-10"): ("Prior-session earnings release", "https://investor.oracle.com/investor-news/news-details/2025/Oracle-Announces-Fiscal-Year-2026-First-Quarter-Financial-Results/default.aspx"),
}


def next_session_table(sessions):
    """Date-only conservative execution proxy for signals using completed daily bars."""
    ordered = sorted(set(sessions))
    if not ordered:
        raise ValueError("No reference sessions")
    return pd.DataFrame({
        "feature_session": ordered,
        "first_usable_session_for_execution": ordered[1:] + [None],
        "rule": "after completed session close; earliest next observed SPY session",
    })


def price_events(model, divergence_threshold=0.01):
    required = {"ticker", "session_date", "split_close_return",
                "provider_all_adjusted_return", "large_return_review"}
    if not required.issubset(model.columns):
        raise ValueError(f"Missing price evidence columns: {required - set(model.columns)}")
    evidence = model[["ticker", "session_date", "split_close_return",
                      "provider_all_adjusted_return", "large_return_review"]].copy()
    evidence["return_difference_pp"] = 100 * (
        evidence.provider_all_adjusted_return - evidence.split_close_return
    )
    evidence = evidence[
        evidence.large_return_review | evidence.return_difference_pp.abs().gt(100 * divergence_threshold)
    ].copy()
    evidence["review_kind"] = evidence.apply(
        lambda r: "large_move_and_adjustment_difference" if r.large_return_review and abs(r.return_difference_pp) > 100 * divergence_threshold
        else "large_move" if r.large_return_review else "adjustment_difference", axis=1)
    evidence["documented_event"] = evidence.apply(
        lambda r: DOCUMENTED_EVENTS.get((r.ticker, r.session_date), (None, None))[0], axis=1)
    evidence["event_source"] = evidence.apply(
        lambda r: DOCUMENTED_EVENTS.get((r.ticker, r.session_date), (None, None))[1], axis=1)
    evidence["move_context"] = evidence.apply(
        lambda r: MOVE_CONTEXT.get((r.ticker, r.session_date), (None, None))[0], axis=1)
    evidence["move_context_source"] = evidence.apply(
        lambda r: MOVE_CONTEXT.get((r.ticker, r.session_date), (None, None))[1], axis=1)
    evidence["price_independently_verified"] = False
    return evidence.sort_values(["session_date", "ticker"]).reset_index(drop=True)


def identity_table(tickers, sec_dir=SEC_DIR):
    mapping = json.loads((sec_dir / "company_tickers.json").read_text(encoding="utf-8"))
    current_ciks = {item["ticker"]: str(item["cik_str"]).zfill(10) for item in mapping.values()}
    rows = []
    for ticker in sorted(tickers):
        submission = json.loads((sec_dir / f"{ticker}_submissions.json").read_text(encoding="utf-8"))
        facts = json.loads((sec_dir / f"{ticker}_companyfacts.json").read_text(encoding="utf-8"))
        cik = str(submission["cik"]).zfill(10)
        rows.append({
            "model_ticker": ticker,
            "sec_cik": cik,
            "sec_entity_name": submission.get("name"),
            "current_sec_mapping_matches": current_ciks.get(ticker) == cik,
            "companyfacts_cik_matches": str(facts["cik"]).zfill(10) == cik,
            "in_current_sec_tickers": ticker in submission.get("tickers", []),
            "sec_former_names_count": len(submission.get("formerNames", [])),
            "documented_history": "FB through 2022-06-08; META from 2022-06-09" if ticker == "META"
                else "Linde plc LIN from 2018-10-31; do not prepend predecessor PX" if ticker == "LIN"
                else "GE spin-offs 2023-01-04 and 2024-04-02" if ticker == "GE" else None,
            "history_source": DOCUMENTED_EVENTS.get((ticker, "2022-06-09"),
                DOCUMENTED_EVENTS.get((ticker, "2018-10-31"),
                DOCUMENTED_EVENTS.get((ticker, "2023-01-04"), (None, None))))[1],
            "full_historical_identity_verified": False,
        })
    return pd.DataFrame(rows)


def run(model_path=MODEL, snapshot_path=SNAPSHOT, sec_dir=SEC_DIR):
    # The existing audit enforces model/interim checksums and row-level price equality.
    previous_audit, _, _ = audit(model_path=model_path, snapshot_path=snapshot_path)
    snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    model = pd.read_csv(model_path, low_memory=False)
    events = price_events(model)
    spy = pd.read_csv(ROOT / "data/interim/prices" / snapshot["dataset_version"] / "daily_prices.csv",
                      usecols=["ticker", "session_date"])
    sessions = next_session_table(spy.loc[spy.ticker.eq("SPY"), "session_date"])
    if not set(model.session_date).issubset(set(sessions.feature_session)):
        raise ValueError("Model has dates absent from SPY reference sessions")
    identity = identity_table(model.ticker.unique(), sec_dir)
    if not identity.companyfacts_cik_matches.all():
        raise ValueError("SEC submissions and companyfacts CIKs disagree")
    summary = {
        "model_sha256": previous_audit["model_sha256"],
        "snapshot_version": snapshot["dataset_version"],
        "provider_asof": snapshot["source_requests"][0]["parameters"]["asof"],
        "modeled_rows": len(model),
        "large_move_count": int(model.large_return_review.sum()),
        "large_move_max_abs_basis_difference_pp": float(events.loc[events.large_return_review, "return_difference_pp"].abs().max()),
        "large_moves_with_dated_public_context": int(events.loc[events.large_return_review, "move_context"].notna().sum()),
        "adjustment_difference_over_1pp_count": int(events.return_difference_pp.abs().gt(1).sum()),
        "documented_action_or_identity_event_count": int(events.documented_event.notna().sum()),
        "current_sec_cik_matches": int(identity.current_sec_mapping_matches.sum()),
        "current_sec_mapping_missing_or_mismatched": identity.loc[
            ~identity.current_sec_mapping_matches, "model_ticker"].tolist(),
        "full_historical_identity_verified": False,
        "all_price_events_independently_verified": False,
        "bar_available_at_populated": False,
        "decision_time_rule": "Completed close-price features are usable for execution no earlier than the next observed market session. This is a date proxy, not an actual data delivery timestamp.",
        "existing_close_to_close_target_executable_at_signal_close": False,
    }
    return summary, events, identity, sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary, events, identity, sessions = run()
    out = args.output_dir or ROOT / "reports/generated" / datetime.now(timezone.utc).strftime("price_reconciliation_%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    events.to_csv(out / "price_events.csv", index=False)
    identity.to_csv(out / "identity_review.csv", index=False)
    sessions.to_csv(out / "decision_sessions.csv", index=False)
    print(json.dumps(summary, indent=2))
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
