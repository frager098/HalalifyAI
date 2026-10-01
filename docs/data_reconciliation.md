# Data reconciliation for the collected Halalify dataset

Revision date: 2026-10-02. Proposed amendment for team review; no peer or domain approval is claimed.

## What changes and why

The original Day 2 documents proposed 40 stocks, Yahoo prices and a 2015 warm-up year. Actual collection uses 50 companies and Alpaca SIP, with history beginning in 2016 and LIN beginning on 2018-10-31. Keep the useful collected data, record a new experiment/dataset version, and do not pretend those choices were the original design.

1. Keep the exact 50 company candidates in `configs/universe.json`. SPY is a separate market reference, never the 51st company or an automatically eligible holding.
2. Fix the main study to 2016-2025. Keep the older downloaded 2026 records as source material, outside this initial training/validation/test experiment.
3. Use the first 60 consecutive observed return intervals (61 closing prices) per instrument as warm-up. With complete coverage from 2016-01-04, the first potentially ready row is the 61st session. LIN must warm up after its own history starts. All 16 feature checks must still pass. Do not create 2015 prices or fill pre-listing LIN dates.
4. Preserve the original train 2016-2020, validation 2021-2022 and test 2023-2025 bounds, starting retained training rows only when features are ready. Preserve session-based label purges and training-only thresholds. No model results have yet established whether these settings perform well.
5. Use Alpaca `adjustment=split` OHLC and matching split-adjusted volume for `close * volume`. Keep a separate `adjustment=all` close as the candidate `adjusted_close` for return calculations. The documented API applies splits, dividends and spin-offs for `all`. Do not add dividends again. Preserve dividend/split action evidence; unknown event coverage remains null, not invented zero/one. Provider-rounded values and all-company action interpretation still require review before claiming full adjustment verification.
6. Normalize source dates to America/New_York sessions; store collection timestamps in UTC. Store immutable original response bytes, request parameters, hashes and package versions.
7. Put evidence/cleaned intermediate files in `data/interim`; only feature/label-ready training datasets go in `data/processed`. Reports go in `reports/validation`. Raw files remain in `data/raw`.

Sources: [Alpaca bars and adjustment definitions](https://docs.alpaca.markets/us/reference/stockbars), [corporate-action endpoint](https://docs.alpaca.markets/us/reference/corporateactions-1). Action query dates filter process dates, so an action's ex-date must be interpreted separately.

## SEC preparation does not invent missing financial amounts

`prepare_sec` reads preserved Company Facts and retains original tags, units, periods, accession numbers, amendments and issuer CIK. It collects a larger set of candidate tags, but these are evidence candidates, not certified consolidated totals.

- Non-USD, invalid periods, inappropriate negative amounts and conflicts within the same filing are quarantined, with reasons. Original values are preserved. Negative net income is allowed when its flow period is valid.
- Facts are first usable at the next exchange session after filing. Acceptance timestamps are null until actually recovered; scope stays unverified until reviewed.
- Revisions in different filings remain separate records. Do not globally choose the latest value and backfill it into history.
- Debt components and alternative cash/revenue concepts are not automatically summed. Four non-overlapping quarters must be reconstructed before annual revenue/profit ratios.
- Missing debt/revenue/receivable fields remain unknown; broader tag extraction does not prove every issuer's mappings are resolved.

Historical XOM needs predecessor CIK `0000034088` for the 2016-2025 study. Current ticker mapping can point to the 2026 successor `0002115436`; that snapshot cannot supply the predecessor's full history. A versioned supplemental downloader retrieves predecessor Company Facts and submissions, without overwriting the old file. [SEC reorganization filing](https://www.sec.gov/Archives/edgar/data/34088/000119312526291986/d70995d8k.htm). The special mapping is scoped to this study; do not reuse it for current 2026 company identity without reviewing effective dates. BAC's issuer name and other corporate-action histories still need individual checks.

## Commands from the repository root

Install project dependencies, then:

```bash
python src/data/download_alpaca.py
python -m src.data.collect_action_evidence
python -m src.data.prepare_sec --input data/raw/sec
python -m pytest
```

The Alpaca command collects the 50 companies plus SPY in one matching version, preserving both price bases. `python src/data/download_spy.py` instead collects SPY only. All runs create new timestamped folders, not overwrite old datasets.

Set `SEC_USER_AGENT` locally to your project name and real contact email before using `python src/data/download_sec.py`. The SEC service requires identification, not an API key. For the supplemental predecessor-only request:

```bash
python -m src.data.collect_sec_snapshot --symbols XOM
```

Pass the resulting predecessor file to `prepare_sec --xom-history PATH_TO_XOM_companyfacts.json` alongside the existing raw folder. It replaces XOM only in the new prepared evidence set, not in original storage. A fresh full SEC snapshot contains submission records for future acceptance-time review, but the current preparer does not yet consume them.

For an older CSV audit, `python src/data/validate_data.py` defaults to `reports/validation` and prefers the interim SEC CSV, falling back to the old processed location. This legacy audit does not by itself validate every new versioned collection or certify screening readiness.

## What remains before training or portfolio claims

Core price forecasting needs validated action/price-basis evidence, pinned complete session metadata, meaningful feature tests and all 16 feature columns, then labels and chronological splits. None of those later model components should be marked complete by this data-reconciliation change.

Fundamental extensions need issuer-by-issuer mappings and compatible financial snapshots. Screening additionally needs dated business activities, prohibited/interest income and the proposed rule profile's domain approval. Do not call an unknown company compliant. Do not make a historical compliant backtest with today's screening verdicts.

The SRS statement about changing classification thresholds by user preference still differs from the fixed-label research design. Portfolio cadence/costs, screening thresholds and that requirement need documented project review; this change does not silently approve them.

Review this task through `feature/data-reconciliation` into `develop`. The existing `feature/spy-data-collection` PR remains separate and unmerged; coordinate its overlapping downloader before merging either PR. No force push or manufactured review is required.

## Executed checks on 2026-10-02

A fresh dual-basis collection produced 127,501 rows across 50 company candidates and separate SPY, with no missing or unexpected sessions in the scoped calendar. The earliest potentially feature-ready session for full-history instruments is 2016-03-31; this does not certify feature readiness. Apple dividend and four-for-one split pilots passed their documented rounding tolerances. Expanded SEC extraction with predecessor XOM retained 77,075 candidate rows and quarantined 22 records; broader candidate extraction explains why these counts differ from the old 39,092-row CSV. Candidates are not reviewed financial totals. BAC submissions confirms CIK70858 and BAC identity; the CompanyFacts display-name discrepancy remains preserved. See reports/validation/reconciliation/reconciliation_summary.json for results and remaining gates. No model or screening verdict was generated.

Automated verification: 15 tests passed, including the existing health test, price-basis separation, pagination, preservation of old files, missing/duplicate sessions, next-session filing availability, negative-net-income handling, conflicting facts and filing revisions. One installed Starlette/httpx compatibility deprecation warning was emitted; the health test passed. Tested environment is Python3.12 with pandas3.0.1/numpy2.3.5 and isolated test dependencies, not a fresh installation of every existing requirements.txt pin.
