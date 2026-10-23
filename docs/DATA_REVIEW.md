# Data review

This document records source integrity, historical price and issuer checks, and the research-only SEC fundamental panel. Generated evidence remains local under reports/generated/.

## Phase 2 decision — 2026-10-22

**Market-only research input is available for phase 3. SEC predictors are not admitted.** This decision supersedes the earlier source-integrity findings below; the earlier reports remain historical evidence. Completion means each phase 2 step has evidence and a disposition, not that every provider value or historical identity is independently certified.

Reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cleaning.txt
.\.venv\Scripts\python.exe -m src.data.validate_data --phase2
.\.venv\Scripts\python.exe -m unittest tests.test_clean_data tests.test_price_reconciliation tests.test_pit_fundamentals -v
```

The final run is `reports/generated/phase2_20261022T060900192314Z/`. Its `phase2_report.json` names the selected cleaned input, hashes, environment, all 14 step dispositions, and phase 3 contract. `output_manifest.json` fingerprints the evidence files. Generated data and reports are ignored by Git; transfer these artifacts separately when another developer needs this exact run.

### Source recovery and selected versions

- Original prices: `data/raw/alpaca/alpaca_sip_20261009T110617242394Z/`.
- Selected restored prices: `data/raw/alpaca/alpaca_sip_20261009T110617242394Z_restored_json_v1/`.
- Reused normalized input: `data/interim/prices/alpaca_sip_20261009T110617242394Z/daily_prices.csv`.
- SEC: `data/raw/sec_snapshots/20261009T110657727507Z/`, with AAPL excluded from the candidate panel.
- Preserved old modeling table: `data/modeling/20261009T115557984450Z/model_dataset.csv`; its SHA-256 remains `ad9b35d6be20564546312259bb75854c4de5c6c3d5a9e5034b7d56e46c9e8a58`.

The original 18 price pages differ byte-for-byte from their acquisition manifests. Serializing their parsed JSON compactly reproduces **the exact original SHA-256 for every affected page**. Eight other pages already match. The restored snapshot contains all 26 original-hash-matching pages and a recovery manifest; original files and expected hashes were not changed. Recovery rejects any candidate that cannot match the old digest. Matching numerical values alone would not be sufficient.

All 26 pages also match the retained normalized fields: split-adjusted open/high/low/close/volume and all-adjusted close. The normalized table does not retain all-adjusted open/high/low/volume, so those columns are not claimed to have been compared. There are no changed retained market values or duplicate raw keys.

AAPL submissions can also reproduce its original hash, but AAPL Company Facts cannot under the tested reconstruction. No trusted second local Company Facts copy was found. The original pair remains excluded from SEC features; a recoverable submissions file does not authenticate the financial values. The other 98 SEC files match their original manifests. No new provider download was needed for market recovery.

### Coverage and exact phase 3 scope

| Check | Result / disposition |
| --- | --- |
| Feed and requested interval | SIP, daily, 2016-01-01 through 2025-12-31; provider `asof=2025-12-31` |
| Cleaned price rows | 127,501: 124,987 company observations and 2,514 SPY observations |
| Company universe | 50 current research names; not a Shariah-compliant universe |
| Observed coverage | 49 companies and SPY: 2016-01-04–2025-12-31; LIN: 2018-10-31–2025-12-31 |
| Exchange calendar | XNYS, exchange-calendars 4.13.2; extraordinary closures included |
| Missing requested sessions | 713 LIN sessions before its documented listing; no unexplained gaps |
| Invalid/quarantined prices, unexpected sessions, zero volume | 0 |
| Large moves over 25% | 9, individually recorded and retained with unresolved independent price verification |
| Adjustment differences over 1 percentage point | 92, assigned interpretations and batches; adjustment verification stays false |
| Historical issuer review | 50 records in five batches; dated exceptions documented, complete history remains open |

The older IEX file described in AGENTS.md is a different dataset, is absent from this checkout, and is not selected. Its mostly-2020 coverage must not be confused with this versioned SIP snapshot.

Use **all non-SPY rows** of the cleaned `prices_clean.csv` named by the final report, with `ticker`, `session_date`, split OHLC, `volume`, and `adjusted_close`; retain provenance and quality flags separately. Use SPY only as a benchmark. Use provider **all-adjusted close consistently** for stock/SPY returns, momentum, and forward labels; it is a provider-adjusted return proxy, not independently certified cash-flow accounting. Do not mix split-close and all-adjusted-close returns.

These are eligible *input rows*, not 124,987 ready-to-train examples. Phase 3 must apply feature warm-up, future-window completeness, and the approved peer-group rules. There are only 49 observed company names before LIN lists: do not invent LIN history or silently redefine a required 50-name label group. The existing model CSV's old labels do not implement the newly approved phase 1 targets.

Predictions use the completed close of session t. Earliest assumed execution is the next observed session; `decision_sessions.csv` records this proxy. Actual `bar_available_at` remains missing. A close-t-to-close-t+20 outcome is a forecast target, not an executable holding return from a signal formed after close t.

### Review dispositions and limitations

`price_event_dispositions.csv` records every flagged event, both price bases, source links where available, a batch, and an unresolved/retained disposition. GE, DHR, and HON separation announcements provide context. Costco's [2017 announcement](https://investor.costco.com/news/news-details/2017/Costco-Wholesale-Corporation-Reports-Special-Cash-Dividend-of-7.00-Per-Share-and-Increase-in-Quarterly-Cash-Dividend-04-25-2017/default.aspx), [2020 announcement](https://investor.costco.com/news/news-details/2020/Costco-Wholesale-Corporation-Declares-Special-Cash-Dividend-of-10-Per-Share-11-16-2020/default.aspx), and [2023 filing](https://www.sec.gov/Archives/edgar/data/909832/000090983223000062/cost-20231213.htm) establish special dividends of $7, $10, and $15. These are candidate explanations for the three COST differences, not certification of their ex-dates or Alpaca adjustment magnitudes. Recurring differences without dated evidence remain distribution candidates, not confirmed dividends.

`identity_review.csv` preserves the META/FB transition, LIN listing, GE/DHR/HON reorganizations, and XOM's study issuer CIK `0000034088`. The [2025 Exxon Mobil filing](https://investor.exxonmobil.com/sec-filings/all-sec-filings/content/0000034088-26-000045/xom-20251231.htm) supports that issuer identifier; it does not provide a complete security-history map. Do not replace the historical issuer merely because a current ticker lookup changes. All full-history flags remain false. Today's 50-name selection introduces survivorship and selection bias.

For SEC, `sec_selected_facts.csv` preserves the concept, USD value, CIK, form, source filename, observation position within that concept's USD observations, period, accession, filing date, and conservative next-calendar-day availability. Only `Assets` and `CashAndCashEquivalentsAtCarryingValue` are candidates. Amended forms are not silently substituted. Repeated comparative periods, revisions, and conflicts are handled before the as-of join. The cash/assets ratio requires the same accession and period, with no future filings used.

`sec_concept_dispositions.csv` covers all 50 companies, including explicit AAPL source exclusions. Debt components are not automatically summed; annual/YTD/quarter revenue is not mixed; restricted cash is not substituted for unrestricted cash; receivables mappings remain issuer-specific. None of these reviewed concepts is an approved predictor. Profit margin and historical market capitalization remain absent.

**Remaining evidence:** restore/reacquire AAPL Company Facts; validate SEC historical filing vintages and issuer links; obtain independent price/corporate-action evidence where needed; document full security histories. These remain limitations or exclusions, not silently repaired facts. `core_ready`, adjustment/identity verification, and SEC training readiness remain false even though the scoped market research gate is open.

### Implementation and verification

The existing validator now orchestrates phase 2; the existing cleaner supports `--market-only` so verified prices are not blocked by an unrelated SEC exclusion. Raw-page comparison, event/identity review, and SEC provenance reuse their existing modules. No new script or model/feature dataset was created. Recovery and cleaning necessarily create separate versioned artifacts so original sources remain immutable.

Fourteen focused tests pass: exact-hash recovery and tamper rejection, market-only checksum enforcement, raw value/key mismatch detection, invalid/conflicting observations, calendar closures, next-session timing, SEC forms/units/accessions, filing availability, and same-statement ratios. The final report also verifies that original input hashes did not change during the run.

---

## Price adjustment, identity and timing


Run `python -m src.data.reconcile_price_history` to recreate this report from the
saved 2026-10-09 Alpaca SIP snapshot, modeling CSV and SEC snapshots. The run
also checks the model and interim CSV checksums and their price agreement.
Example output: `reports/generated/price_reconciliation_20261019T063028Z/`.

### What the saved data establishes

- The model has 124,987 rows for 50 stocks. The request used `feed=sip`,
  `adjustment=split` and `adjustment=all`, and `asof=2025-12-31`. Its observed
  coverage is 2016-01-04 to 2025-12-31, except LIN begins 2018-10-31.
- The nine moves over 25% appear in both price bases. Their largest absolute
  return difference between bases is **0.047 percentage points**. Seven have
  a dated company earnings release near the event; COP and SLB have no company
  event established by this review. The releases provide context only. None
  independently verifies the historical closing prices.
- There are **92** days where the split adjusted and fully adjusted daily
  returns differ by more than one percentage point. These differences are
  candidates for dividends or spin offs, rather than automatic bad rows.
  [Alpaca's bars documentation](https://docs.alpaca.markets/us/reference/stockbars)
  says `all` includes splits, cash dividends and spin offs. We found dated
  issuer evidence for four of those rows: GE 2023-01-04 and 2024-04-02,
  DHR 2023-10-02, HON 2025-10-30. The remaining 88 have no individual
  corporate-action reconciliation in this report. Do not change their values
  or declare adjustment verification complete on this evidence alone.
- Current SEC companyfacts and submissions CIKs agree for 50/50 tickers;
  the saved current SEC ticker lookup resolves 49/50. XOM is absent there and
  is also absent from its submissions `tickers` list, although its companyfacts
  and submissions agree on CIK 0000034088. This is a source-mapping exception,
  not evidence that historical XOM prices should be removed.

### Historical identity findings

[Alpaca's `asof` setting](https://docs.alpaca.markets/us/reference/stockbars)
may return past ticker bars under the requested later symbol. Hence
`instrument_id=US_<current ticker>` does not establish an immutable security
identity. [Meta's issuer announcement](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx)
states FB changed to META before trading on 2022-06-09 with the same Class A
shares and CUSIP. The pre-change model rows labeled META represent historical
FB trading; ticker labels must be displayed as-of-date in historical reports.

[Linde's issuer announcement](https://www.linde.com/news-and-media/2018/business-combination-between-praxair-and-linde-ag-successfully-completed)
states Linde plc began NYSE trading as LIN on 2018-10-31 after a business
combination. The model correctly has no earlier LIN rows. Do not append
Praxair PX bars merely to create a longer history. [GE](https://www.ge.com/faq)
kept the GE ticker after 2023 and 2024 spin offs, but its business and price
basis changed. That requires explicit treatment in interpretation and
portfolio backtests. The current SEC snapshot alone cannot verify complete
historical issuer identity for all 50 names.

### When a daily bar is usable

A signal calculated with session **t's closing price** is treated as usable
for execution no earlier than the next observed market session. The generated
`decision_sessions.csv` maps each SPY reference session to that next session;
the final date has no next session in the saved dataset. This is a conservative
date rule, not an observed provider delivery timestamp. `bar_available_at`
stays blank and `core_ready` stays false.

The existing 20-session return target is the fully adjusted close at `t+20`
divided by the fully adjusted close at `t`, minus one. It is a valid forecast
label for a signal formed **after** t closes. It is not the return a strategy
can lock in by trading at t's already observed close. Before calling monthly
ranking a backtest, define the entry price at the next tradable session and
recompute realized holding returns from that entry, with costs and the
historical compliant universe.

### Output files and remaining work

`price_events.csv` lists both review types, basis differences, and sourced
issuer context. `identity_review.csv` compares current SEC identifiers and
records known history. `decision_sessions.csv` gives the next-session rule.
`summary.json` gives counts and explicitly leaves verification flags false.

For model-ready data, obtain independent corporate-action records and an
independent historical price source for disputed moves, build a dated ticker
and issuer map for all 50 symbols, and document the actual bar availability
and execution convention. Then rerun features, labels and evaluations on a
new versioned dataset; retain the present model dataset as the baseline.

---

## SEC point in time fundamentals


Run `python -m src.data.build_pit_fundamentals` to reproduce steps 4 and 5
from the preserved 2026-10-09 SEC snapshot. The 2026-10-19 run saved its
report under `reports/generated/pit_fundamentals_20261019T064428Z/`.
The existing price-based modeling CSV and its labels were not modified.

### Source integrity first

The saved modeling CSV matches its own checksum. However, 18 of 26 Alpaca
raw JSON pages and the AAPL SEC companyfacts and submissions files do **not**
match their manifest byte checksums. The existing full cleaner stops on that
discrepancy. A separate value-by-value replay confirmed that the currently
saved Alpaca raw pages still agree with both columns of the interim price CSV;
this does not repair their provenance. AAPL is excluded from the SEC feature
candidate panel. The other 98 SEC files (49 companies) match their manifest.
The report saves every expected and observed hash.

### Fact semantics selected for the candidate panel

Only US-GAAP `Assets` and `CashAndCashEquivalentsAtCarryingValue` were selected.
Both are instantaneous USD balance-sheet concepts. The script accepts only
10-K/10-Q facts with a valid accession, nonfuture period end and sensible
nonnegative values. Within a filing, it uses the latest reported period,
removing older comparative balances. Conflicting values for the same filing,
period and concept are quarantined. For a session, it selects the latest
financial period available by then; a late amendment to an older period
cannot replace a newer balance sheet.

The file date alone does not establish when during that date the filing was
available. Therefore facts become eligible on the **next calendar day**;
the first market session on or after that day can use them. Every selected
fact retains its filing date, available date, accession and period end. The
`cash_to_assets` ratio appears only when cash and assets are from the **same
accession and period**, and the result lies in [0, 1]. This rule is for a
financial-strength research feature, not a Shariah threshold.

The [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
explains that Company Facts contains concepts, units and observations across
filings and that its live JSON is updated throughout the day. A current
Company Facts snapshot with accession numbers is useful for historical
reconstruction, but it is not itself an archived snapshot from each past date.
The panel therefore keeps vintage verification false.

### Result and limitations

The candidate panel has 124,987 ticker/date rows aligned to the existing
model dataset. It contains 121,856 rows with an assets value, 121,269 with a
cash value and 106,276 with a same-filing `cash_to_assets` ratio. AAPL feature
values are blank due to the failed SEC checksums. No fact conflicts arose
under the narrow selected mapping.

Debt and revenue remain in `concept_review.csv` for study. Debt requires
combining current and noncurrent concepts without double counting, and
revenue is a duration value whose annual/quarterly semantics must be
normalized. The alternative cash concept includes restricted cash, so it
was not silently substituted for unrestricted cash. Profit margin and
historical market capitalization are not available from this panel.

The panel is **research-only**, with `ready_for_model_training=false`.
Recover or re-download the mismatched raw files into a new immutable snapshot,
confirm historical issuer identities and filing vintages, then version the
accepted feature dataset. Only after that should SEC predictors enter a
model comparison. Preserve the existing price-only scores as the baseline.



