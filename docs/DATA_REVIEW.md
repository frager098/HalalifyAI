# Data review

This document records source integrity, historical price and issuer checks, and the research-only SEC fundamental panel. Generated evidence remains local under reports/generated/.

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



