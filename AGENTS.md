# HalalifyAI - shared project context and agent guidance

## Training input repair 2026-10-08

Read docs/training_data_repair.md before running the model notebook. Reviewed prototype commit 6c417db continued after failed action/audit commands and set absent verification flags True. Never retain that fallback. src/data/training_inputs.py requires explicit flags and audited-output routing; false/unknown evidence must exclude affected windows or stop preparation. The repaired notebook has no saved outputs and has not completed a full Colab/API/ONNX execution.

Retained source reconstruction and audit reproduced the previous audited CSV exactly;118643 eligible rows. Full tests:59 passed; all22 documented train/validation classifier fits rerun. Return validation accuracy36.882%, macroF1 .362892; risk60.675%, .577060. No new test scoring, accuracy improvement, peer approval, deployment or screening approval claimed. Newer user Colab input SHA7726381a459599eb5bf8e3ee5aa202a74cdb26fa4a2b2e3bad69a5a1d070b0f3 remains unavailable locally/GitHub. Do not conflate snapshots. Original user checkout and GitHub remain unchanged until installation/publication is actually performed.

Updated: 2026-10-03 | Handoff version: 2.1

Status: dated evidence plus proposed research specifications. Published data-readiness branch cb0e2f0 was verified on 2026-10-02. New SEC evidence work is prepared on feature/sec-screening-evidence. No develop merge or domain approval is confirmed.

Current screening evidence addition: read docs/sec_screening_evidence.md, configs/sec_screening_evidence.json and reports/validation/screening_evidence/sec_2015_2025_v2/coverage.json. Original annual/quarterly filings, business excerpts and revenue/income candidates are preserved with issuer, reporting period, availability, dimensions and SHA-256 provenance. Large files reside in data/raw and data/interim, never Git. The source ZIP is read directly by the extractor; do not make the beginner user manually unpack/copy multiple bundles. Standard/edition, prohibited-income completeness, company-specific mappings, historical business continuity and peer approval remain pending. Empty approved amounts and needs_review are intentional, not evidence of zero income. This current section supersedes older claims that business evidence has not been collected; it does not supersede approval requirements or certify historical eligibility.

Read current sections together; historical data snapshots are explicitly labeled. The attached original has been preserved. Repository links are discovery pointers, not permission to merge/publish.


## Purpose of this file

This file gives AI the working context, technical decisions, data
facts, architecture, constraints, and unresolved issues for the
HalalifyAI Final Year Project.

Treat this as project guidance, not as permission to blindly preserve
mistakes. If an existing requirement, implementation choice, or document
conflicts with sound ML/software-engineering practice, identify the
conflict and explain the proposed correction before making a major
architectural change.

Do not invent missing business rules, Shariah thresholds, dataset facts,
or experimental results.

------------------------------------------------------------------------

# 1. Project Identity

**Project name:** Halalify AI

Other titles used in project documents: - AI-Powered Shariah-Compliant
Investment Assistant - Shariah-Compliant Smart Portfolio Management
System

**Project type:** University Final Year Project (FYP)

**Initial market:** U.S. equities only.

The project is an academic/research prototype. It is not a brokerage and
does not execute real trades.

------------------------------------------------------------------------

# 2. Main Goal

HalalifyAI should help a user evaluate U.S. stocks and construct a
Shariah-compliant portfolio.

The intended high-level pipeline is:

1.  Collect historical stock-market data.
2.  Collect historical company financial/fundamental data.
3.  Clean and validate the datasets.
4.  Engineer market and fundamental features.
5.  Create future return and future risk labels.
6.  Train ML models.
7.  Predict expected return class and risk class.
8.  Apply rule-based Shariah screening separately.
9.  Build a portfolio using only compliant stocks.
10. Adjust portfolio construction according to user risk preference.
11. Backtest the historical strategy.
12. Provide understandable explanations through APIs/UI.

Return/risk ML classification and Shariah screening are separate
systems.

------------------------------------------------------------------------

# 3. Repositories and Architecture

## AI repository

Repository: `https://github.com/frager098/HalalifyAI`

HalalifyAI should own: - historical data processing relevant to ML -
feature engineering - label creation - ML training - ML inference -
Shariah screening logic - portfolio optimization - backtesting -
explainability/XAI - AI-facing FastAPI endpoints

## Backend repository

Repository: `https://github.com/SheikhUzairRaza/HalalifyAPI`

Backend technology currently includes: - Node.js / Express - MySQL /
Sequelize - JWT/local authentication - Google/Firebase authentication -
onboarding information such as risk preference, goals, and screening
strictness - Alpaca/Finnhub integrations for current stock information -
Swagger - Zod validation - centralized error handling

Target architecture:

Frontend → HalalifyAPI (Node/Express application backend) → HalalifyAI
(Python/FastAPI AI service)

The backend should generally own: - authentication - users -
persistence - application workflows - scheduling/provider integration as
appropriate

The AI service should generally own the ML/research logic listed above.

Do not collapse these repositories/services into one without a strong
reason and explicit approval.

------------------------------------------------------------------------

# 4. Current Prototype Scope

The initial research universe contains approximately 30--50 U.S. stocks.
The current working universe is 50 stocks.

Current 50 tickers:

AAPL, MSFT, NVDA, AMD, AVGO, ORCL, ADBE, CRM, CSCO, INTC, GOOGL, META,
NFLX, AMZN, TSLA, HD, LOW, NKE, SBUX, MCD, COST, WMT, JNJ, LLY, ABBV,
MRK, TMO, ABT, DHR, CAT, DE, HON, UPS, UNP, GE, XOM, CVX, COP, SLB, JPM,
BAC, GS, MS, V, MA, PG, KO, PEP, LIN, NEE.

Important: - This is an initial research universe. - These stocks are
NOT assumed to all be Shariah compliant. - The universe still needs an
academically defensible selection methodology. - Survivorship bias must
be documented. - Do not describe the universe as a list of compliant
stocks.

Prototype settings: - Frequency: daily market data - Intended historical
start originally: approximately 2016 - SIP coverage is now observed from 2016 for 49 companies; LIN begins in late 2018. See section 5. - Prediction horizon: 20
future trading days - Return classes: Low / Medium / High - Risk
classes: Low / Medium / High - Plan portfolio rebalancing: monthly; proposed experiment: every 20 exchange sessions (review required) -
No intraday trading - No live brokerage execution - Deep learning is not
required for the initial prototype.

------------------------------------------------------------------------

# 5. Alpaca market data: current and historical snapshots

Alpaca supplies daily prices and trading volume. SIP is consolidated data from multiple US exchanges; IEX is a single exchange feed. Neither feed is a benchmark. SPY is the separate market-reference ticker.

Historical snapshots must not be confused:

| Snapshot | Rows | Instruments and coverage | Status |
| --- | ---: | --- | --- |
| Original IEX | 77,455 | 50 companies, mostly 2020-07-27 to 2026-09-28; CSCO has one isolated earlier row | Superseded for the current historical collection |
| Replacement SIP company CSV | 134,237 | 49 companies: 2016-01-04 to 2026-09-28, 2,699 sessions each; LIN: 2018-10-31 onward, 1,986 sessions | Basic and scoped calendar checks performed; original seven-column all-adjusted schema |
| Earlier separate SPY SIP CSV | 2,514 | 2016-01-04 to 2025-12-31 | Basic/calendar checks passed; requested 2015 was not returned |
| New reconciliation collection | 127,501 | 50 companies plus separate SPY, fixed 2016-2025 period; 50 instruments have 2,514 sessions, LIN has 1,801 | Separate price bases collected; not model-ready |

The newest research snapshot is not smaller because data were arbitrarily deleted: it stops at 2025-12-31 and includes SPY separately. Preserve the 2026 records in their original snapshot. LIN refers to the current Linde listing with observed history beginning 2018-10-31. Do not invent prices before its available history or splice predecessor histories without reviewed identity/action methodology.

The original company CSV has date,ticker,open,high,low,close,volume and adjustment=all. It cannot directly supply the dictionary's dollar-volume feature because its close includes dividend adjustment.

The new collector requests two series from Alpaca SIP:
- adjustment=split: non-dividend-adjusted OHLC with matching split-adjusted volume; normalized close.
- adjustment=all: split/dividend-adjusted close; normalized adjusted_close, used for return-based calculations after verification.

Never duplicate one column into both price types. Preserve provider pages, request parameters, timestamps and SHA-256 hashes. Dividends are cash distributions; splits change the number of shares and quoted price without, by themselves, creating a gain or loss. Validate actions and price/volume bases before claiming full readiness. Only an AAPL dividend/split pilot is verified so far; global adjustment verification is false.

No 2015 warm-up was obtained. Proposed experiment v1.1 uses the first 60 consecutive observed sessions as warm-up, with the first potential complete feature date 2016-03-31 for full-history instruments. This is an earliest possible date, not evidence that features have been produced.

# 6. Data Source 2 --- SEC EDGAR Company Fundamentals

Purpose: Historical company financial condition/fundamentals.

Source: SEC EDGAR Company Facts API.

Typical endpoint:
`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Ticker-to-CIK mapping comes from SEC company ticker data.

Raw SEC files should remain immutable under a structure similar to:

`data/raw/sec/<TICKER>_companyfacts.json`

Use an appropriate identifying SEC User-Agent/contact when downloading
data.

## XBRL

XBRL means: eXtensible Business Reporting Language.

It provides standardized computer-readable concepts/tags for financial
information.

Examples: - Assets - CashAndCashEquivalentsAtCarryingValue -
AccountsReceivableNetCurrent -
RevenueFromContractWithCustomerExcludingAssessedTax

## Filing

A filing is an official report submitted by a public company to the SEC.

Important forms currently used: - 10-Q = quarterly report - 10-K =
annual report

The filing date is extremely important because it represents when
information became publicly available.

------------------------------------------------------------------------

# 7. SEC datasets: original extraction versus expanded evidence

Original long-format extraction: 39,092 rows, 50 companies, 13 columns:

```text
ticker,company_name,field,sec_concept,value,unit,period_start,period_end,filing_date,form,fiscal_year,fiscal_period,accession_number
```

Original field coverage: assets/cash 50 companies, debt candidates 41, revenue 40, receivables 36. Units: 39,084 USD, six EUR and two CAD. This file was historically saved under data/processed but is extracted evidence, not a model-ready matrix.

Expanded reconciliation extraction: 77,075 retained candidate facts and 22 quarantined observations. Candidate coverage: assets, cash, debt components and net income for 50 companies; revenue 49; receivables 37. These counts mean at least one candidate fact exists, not complete historical coverage or reviewed totals.

Quarantine reasons: ten negative/ambiguous observations, eight non-USD observations, two period-end-after-filing observations, one nonpositive-assets observation, one missing duration start. Preserve questionable source records separately; do not repair values by guessing, taking absolute values or converting unknown currency amounts automatically.

Changed values across filings may be restatements or context differences. The old validation reported 684 changed-value groups and 33 missing company-field combinations; these are old-extraction diagnostics, not the current expanded extraction's counts. REVIEW means investigation is required; a successful script run is not universal data acceptance.

XOM: the original mapping used successor CIK 0002115436, with only eight original extracted facts filed in 2026. A separate SEC snapshot for predecessor CIK 0000034088 recovered historical candidates with filing dates 2009-08-05 to 2026-05-04. This mapping is explicitly scoped to the 2016-2025 study and supported by reorganization evidence; preserve both identities and sources.

BAC: SEC submissions identifies BANK OF AMERICA CORP /DE/, CIK 0000070858, ticker BAC, while CompanyFacts labels BofA Finance LLC. Preserve both source labels and the discrepancy; do not silently rewrite the CompanyFacts response or declare financial identity completely resolved.

Expanded evidence retains source concepts, units, periods, filing versions, accession numbers, CIK/source links, identifiers, availability sessions and review status. Retained facts remain unreviewed candidates. Debt totals, compatible financial snapshots and trailing-twelve-month flows are not certified.

# 8. SEC Extraction Mapping

Current initial mapping is approximately:

``` python
CONCEPTS = {
    "total_assets": ["Assets"],
    "total_debt": [
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent"
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet"
    ],
    "accounts_receivable": [
        "AccountsReceivableNetCurrent"
    ]
}
```

This is an initial mapping, NOT a guaranteed complete/correct mapping
for all issuers.

Specific concerns: - Total debt may require combining current and
noncurrent debt. - Alternative debt concepts may exist. - Revenue is a
duration fact and must use correct period semantics. - Cash concepts can
have different meanings. - Accounts receivable concepts vary between
issuers. - Duplicate/restated/amended filings must be handled carefully.

Do not blindly pivot the long dataset into ML format until these
semantics are validated.

------------------------------------------------------------------------

# 9. Meaning of Important SEC Columns

`field` = HalalifyAI's normalized/simple financial-field name.

`sec_concept` = original SEC XBRL concept that produced the value.

`value` = reported financial value.

`unit` = reporting unit such as USD.

`period_start` = beginning of the period for duration facts.

`period_end` = financial period/date the fact describes.

`filing_date` = date the information became publicly available through
the filing.

`form` = filing type, primarily 10-Q or 10-K.

`fiscal_year` = company's fiscal year.

`fiscal_period` = fiscal period such as Q1/Q2/Q3/FY.

`accession_number` = unique SEC filing identifier.

------------------------------------------------------------------------

# 10. Historical information availability: mandatory rule

Never use information before it was publicly available. Financial period_end describes the accounts; it does not establish when investors knew them.

For this dictionary, available_from_session is conservatively the first exchange session AFTER the filing/acceptance calendar date. Use an acceptance timestamp when recoverable; preserve null if unknown. Do not use a same-day filing merely because filing_date <= prediction_date.

Example: quarter ends 2024-03-31, filing date 2024-05-01. It is unavailable on 2024-04-15 and is usable from the next exchange session after May 1, subject to all other evidence checks.

Join by available_from_session <= feature/assessment date. Preserve filing versions so a later correction becomes available only later; never choose the globally latest restatement for every historical date. Today's Finnhub metrics and company descriptions cannot be backfilled into historical rows.

# 11. Raw / Interim / Processed Data Philosophy

Recommended structure:

`data/raw/` - original provider responses/downloads - do not manually
modify

`data/interim/` - extracted/normalized intermediate datasets

`data/processed/` - cleaned ML-ready feature/label datasets

Raw data should remain immutable for reproducibility and auditing.

Do not overwrite source data during cleaning.

------------------------------------------------------------------------

# 12. Data Validation Requirements

Before ML training, validate at least: - duplicate records - invalid
dates - impossible/negative values where inappropriate - missing
values - ticker coverage - date coverage - gaps - market-data ordering -
duplicate SEC facts - amended/restated filings - XBRL concept mapping -
period semantics - unit consistency - filing-date availability - annual
versus quarterly values

Log/report important data-quality decisions.

------------------------------------------------------------------------

# 13. Exact core market features and formulas

The dictionary defines exactly 16 ordered core predictors. Let P be validated adjusted_close, C be non-dividend-adjusted split-consistent close, V matching volume, and r_t=P_t/P_(t-1)-1. Values are decimals, calculations float64, daily sample volatility uses ddof=1 and annualization sqrt(252).

| Order | Field | Definition |
| --- | --- | --- |
| 1-4 | ret_1d, ret_5d, ret_20d, ret_60d | P_t/P_(t-k)-1 for the named k |
| 5-6 | vol_20d, vol_60d | Sample standard deviation of the named trailing daily-return window times sqrt(252) |
| 7 | downside_dev_20d | sqrt(mean(min(r,0)^2)) over all 20 returns, including zeros, times sqrt(252) |
| 8 | max_drawdown_60d | Positive maximum peak-to-trough fractional loss across 61 adjusted closes |
| 9-10 | price_sma20_ratio, price_sma50_ratio | P_t/mean(last k adjusted closes)-1 |
| 11 | rsi_14 | Wilder RSI: seed from 14 changes, recursively update average gains/losses with 13/14 weight |
| 12 | volume_ratio_20d | V_t/mean(last 20 split-consistent volumes) |
| 13 | log_dollar_volume_20d | ln(1+mean(C*V over 20 sessions)/1 USD) |
| 14 | beta_60d | Sample covariance(stock, SPY daily returns)/sample variance(SPY), paired over 60 returns |
| 15 | market_ret_20d | SPY adjusted-close 20-session return |
| 16 | market_vol_20d | SPY trailing 20-return sample volatility times sqrt(252) |

RSI special cases: no losses =>100, no gains =>0, both zero =>50; reset after a gap and require initialization again. Verify these formulas against the versioned dictionary before implementation.

Sixty returns require 61 consecutive closes. Use an exchange-session calendar, not the next available provider row. Missing prices invalidate affected windows; do not forward-fill market gaps or future targets. Paired SPY windows must match dates; zero market variance invalidates beta. Dollar volume requires verified matching price/volume bases. All 16 must be finite and validated before core_ready.

No duplicate momentum features, ticker codes, static study groups, screening results, future targets or predictions in core inputs. Study groups remain diagnostics/allocation metadata. Features are not implemented yet.

# 14. Optional fundamental and macro extensions

Core Week 2 market modeling can proceed once its own input gates pass; it does not require all optional fundamental features or a finished historical screening engine.

The documented fundamental extension has four ratios: reviewed debt/assets, reviewed cash/assets, net_income_TTM/revenue_TTM, and revenue_TTM/prior_year_TTM-1. TTM means trailing twelve months, assembled from four compatible non-overlapping quarters. Annual and year-to-date revenue must not be blindly summed. Net income can legitimately be negative; missing data is not zero.

Net income is now extracted as candidate evidence, but reviewed TTM profit margins are not produced. Historical market cap/shares are not required for core_v1 or the proposed asset-denominator screening profile. Add them only if a later declared feature/rule requires them.

Optional macro fields are FRED VIXCLS and DGS3MO with dated release/vintage availability, next-session treatment for date-only releases and at most five-session carry. VIX is index points; treasury annual percentage is divided by 100. These optional datasets have not been collected here.

Experimental predictor imputation, if used, is fitted on training data only with missing indicators. It must never fill unknown screening evidence to assert compliance. Compare optional features on matching validation rows, with coverage reported.

# 15. ML Targets / Labels

The initial ML design uses two separate prediction problems.

## Return target

For date t, calculate future return over the next 20 trading days.

Conceptually:

`future_return_20d = price(t+20) / price(t) - 1`

Then convert the continuous future return into: - Low - Medium - High

## Risk target

Calculate realized volatility over the future 20-trading-day period.

Then convert it into: - Low - Medium - High

Return and risk should be modeled separately.

Important: Thresholds used to convert continuous targets into
Low/Medium/High must be learned/calculated using training data only.

Do not use validation/test data to establish class thresholds.

------------------------------------------------------------------------

# 16. ML Models

Initial baseline/candidate models: - Logistic Regression - Random
Forest - HistGradientBoosting

Deep learning is not necessary for the initial academic prototype.

Start with interpretable/strong classical baselines.

Maintain separate: - return model - risk model

Evaluate models before deciding which to use.

------------------------------------------------------------------------

# 17. Chronological partitions and purging

Proposed fixed study: initial training 2016-2020, validation 2021-2022, final test 2023-2025. Only valid complete windows enter. Apply the same date partition to all stocks; never randomly mix future and past rows.

Targets use exactly 20 consecutive future sessions. Purge any fitting/selection row whose label_end_date is on or after the next partition start. A 20-row gap in a stacked 50-stock table is not a 20-session gap. Split unique dates and enforce label-end conditions.

Fit scalers, optional imputers, selectors and pooled linear-interpolation 1/3 and 2/3 target quantiles on retained initial training rows only. Class order [low, medium, high]: low <= first cutoff, medium > first and <= second, high > second. Halt equal cutoffs. Save numeric boundaries; none have been fitted yet.

After validation-only selection and freezing, final models may refit eligible 2016-2022 development rows with label_end_date before test start, retaining original class boundaries. Test results are examined only after freezing; disclose any earlier test inspection. Last 20 raw sessions have no mature 20-session labels.

# 18. Evaluation

Planned classification metrics: - Macro F1 - per-class precision -
per-class recall - confusion matrix

Accuracy alone is not enough, especially if classes are imbalanced.

Keep experiment configuration reproducible: - feature version - split
dates - label thresholds - model hyperparameters - random seeds where
applicable - dataset version

------------------------------------------------------------------------

# 19. Shariah Screening

Shariah screening is rule-based and separate from ML return/risk
prediction.

The ML model may learn from stocks that are later rejected by Shariah
screening, unless the final approved methodology explicitly changes
this.

However: **the final recommended/optimized portfolio must contain only
stocks that pass the selected Shariah methodology.**

A recognized methodology/standard such as AAOIFI has been discussed, but
the exact standard, version, formulas, thresholds, and treatment rules
have NOT yet been finalized.

Therefore: - do not invent Shariah thresholds - do not silently choose a
standard - do not hard-code guessed ratios - require an explicit
documented methodology before finalizing the screening engine

The implementation should make screening rules configurable/versioned
where practical.

------------------------------------------------------------------------

# 20. Risk Preference

User risk preference is intended to affect portfolio construction.

Possible preferences: - conservative - moderate - aggressive

Important design concern:

An SRS requirement previously suggested changing ML classification
thresholds based on the user's risk preference.

This is scientifically confusing because the meaning of a model's
High/Medium/Low prediction should ideally remain stable.

Preferred design direction: - keep ML return/risk class definitions
stable - let risk preference change portfolio
constraints/objective/weighting

Example: A conservative investor may receive lower exposure to stocks
classified as high risk.

Do not implement risk-preference-dependent ML class definitions without
explicit review/approval.

------------------------------------------------------------------------

# 21. Portfolio Optimization

Portfolio input should include only Shariah-compliant candidates.

Initial constraints: - weights \>= 0 - weights sum to 1 - maximum
position-size constraint - diversification constraints

Risk preference should influence portfolio construction.

Avoid implying guaranteed returns.

The system should explain why holdings/weights were selected when
possible.

------------------------------------------------------------------------

# 22. Backtesting

Backtesting must recreate what would have been historically knowable.

At each historical rebalance date: 1. use only market data available by
that date 2. use only SEC filings available by that date 3. generate
features 4. generate model predictions 5. apply the historical Shariah
screen 6. construct the portfolio 7. hold/rebalance according to the
strategy 8. measure subsequent performance

Planned outputs: - total return - annualized return - volatility -
Sharpe ratio - maximum drawdown - turnover - holdings

Baseline: Compare against an equal-weight compliant portfolio.

Avoid future leakage in every stage.

------------------------------------------------------------------------

# 23. Survivorship Bias

The current 50-stock universe was selected as a practical research
universe and consists largely of companies known today.

This can introduce survivorship/selection bias when testing historical
periods.

Document this limitation clearly.

Do not claim the backtest represents an unbiased historical simulation
of the entire U.S. stock market.

A more rigorous future version could use point-in-time index/universe
membership.

------------------------------------------------------------------------

# 24. API Direction

The AI service is expected to use Python/FastAPI.

Possible high-level endpoints: - health - screen - predict - portfolio
optimize - backtest

Exact endpoint names/contracts may evolve.

Keep ML/business logic separated from HTTP route code where practical.

------------------------------------------------------------------------

# 25. Existing Backend Gaps Observed Previously

At the time of the earlier review, HalalifyAPI had application/backend
functionality but did not yet contain the full AI pipeline.

Previously observed gaps included: - no historical ML pipeline - no
complete feature-engineering pipeline - no label-generation pipeline -
no trained return/risk models - no Shariah engine - no portfolio
optimizer - no backtesting engine - no XAI implementation - no completed
AI-service integration - automated tests were not established
(`npm test` was a placeholder) - admin refresh routes needed security
review - `.env.example` needed review for provider variables -
`api_research.md` had unresolved merge-conflict markers during an
earlier review

These observations may become stale as development continues.

Before acting on them, inspect the current repository state.

------------------------------------------------------------------------

# 26. Current Provider Roles

Keep provider responsibilities clear.

## Alpaca

Historical/current market-price data as configured by the project.

For ML: - OHLC - volume - market-derived features

## SEC EDGAR

Historical point-in-time company financial statements/fundamentals.

For ML/Shariah: - assets - debt - cash - revenue - receivables -
additional validated fundamentals later

## Finnhub

The backend has used Finnhub for current fundamentals/metadata.

Critical warning: Do NOT take today's/current Finnhub fundamentals and
backfill them into historical ML dates.

That would create future leakage.

Historical ML fundamentals must be point-in-time.

------------------------------------------------------------------------

# 27. Environment / Python

Project documentation previously recommended Python 3.11/3.12.

A developer machine was observed using Python 3.13.x.

Prefer aligning with the project's supported/reproducible Python version
unless dependencies have been deliberately verified on 3.13.

Use a virtual environment, e.g.:

`.venv`

On Windows PowerShell:

`.\.venv\Scripts\Activate.ps1`

Do not commit secrets or the virtual environment.

------------------------------------------------------------------------

# 28. Secrets and Git Safety

Never commit: - Alpaca API secret - API keys - tokens - passwords -
`.env` - credentials

Use `.env` locally and keep safe templates in `.env.example` without
real secrets.

Before adding large raw data to Git, check repository policy and
`.gitignore`.

Raw SEC JSON and large generated datasets may not belong in normal Git
history.

Prefer committing: - downloader scripts - extraction scripts -
processing code - schemas - small reproducible samples if needed -
documentation

Do not commit large datasets blindly.

------------------------------------------------------------------------

# 29. Git workflow and current publication state

Use focused feature branches from updated develop, meaningful commits and relevant tests; open a PR targeting develop, review/reproduce, then merge after actual authorization and required approval. Stable demonstrated weekly work goes into main. Do not directly push task work into develop or force-push shared history.

Muhiddin clarified on 2026-10-02 that he is currently the only person working on these AI tasks. The plan describes two AI developers, but that is not proof a second reviewer is available. Record honest self-review when working alone; seek an independent review for the plan's peer-review gate when a teammate joins. Never invent teammate approval. A teammate receiving this handoff has not automatically become a reviewer or approved methodology.

Current evidence:
- feature/spy-data-collection was pushed; commits 897aaf1 and 1c04f6a added SPY code and moved validation reports into reports/validation.
- feature/data-reconciliation was created from develop 255436b. The patch was applied locally, then the user successfully pushed it and reported a clean working tree tracking origin/feature/data-reconciliation.
- Local reconciliation commit checked for this handoff: 741f60c. The isolated deliverable commit fbfb725 has equivalent patch work but a different commit identity.
- No PR creation, approval or merge into develop/main has been confirmed. Do not describe the feature work as merged. Live remote state was not rechecked for this handoff; verify before future repository edits.

Applying git am changed local files first; git push then uploaded them. GitHub viewing another branch can hide the changes. Switching branches also changes tracked local code, while ignored datasets generally remain.

Code, configuration, safe tests and selected reports were pushed. Raw and interim datasets were supplied separately in a ZIP and are ignored by Git. Do not assume they exist on a teammate's machine or in Muhiddin's original project merely because the branch was pushed.

# 30. Joining financial evidence and market dates

For each instrument/session calculate market features using information available by that session. If using the optional financial extension, select compatible reviewed financial evidence with available_from_session <= session, preserving provenance and versioned mappings.

Resolve issuer identity, period semantics, cash alternatives, debt components, annual/YTD/quarter flows, units, amendments and missingness before constructing financial snapshots. Do not sum overlapping alternatives or blindly pivot candidate facts into certified totals. Stable instrument IDs and ticker/CIK history require review; current US_TICKER IDs are provisional.

The first core market experiment remains a separate track from fundamental extensions and historical compliance eligibility.

# 31. Plan sequence and current next work

Week 1: scaffold, reproducibility, experiment/dictionary, collection/validation and approved screening prototype. Week 2: market features, 20-session labels, chronological baselines/candidate models. Week 3: optional fundamentals, error analysis, explanations, frozen final evaluation and portfolio/backtest comparisons. Week 4: typed FastAPI/artifact loading, integration, demo and release documentation.

Week 1 is not fully complete merely because collection and validation scripts exist; screening approval and fresh-environment reproducibility remain unestablished. No Week 2 feature/label/model milestone is complete.

Next concrete work: verify delivered datasets are present, review reconciliation outputs and unresolved identities/actions, complete relevant price/action checks, then implement/test the exact 16 market features in src/features and future targets/splits in src/labels. Preserve remaining financial and screening review items on their separate tracks. Do not train directly from the old extracted SEC CSV.

# 32. Coding Expectations for Codex

When modifying this project:

1.  Read the relevant existing code before editing.
2.  Prefer small, reviewable changes.
3.  Explain major architectural changes.
4.  Do not silently change project scope.
5.  Do not fabricate dataset results.
6.  Do not invent financial/Shariah rules.
7.  Protect against look-ahead leakage.
8.  Add clear comments where financial/ML logic is non-obvious.
9.  Use beginner-readable code where possible.
10. Add tests for important transformations.
11. Keep functions/modules focused.
12. Preserve reproducibility.
13. Validate inputs and fail clearly.
14. Avoid unnecessary dependencies.
15. Keep secrets out of source control.
16. Do not delete raw data or existing work without explicit
    reason/approval.
17. Before implementing a requested change, inspect whether it conflicts
    with this context or current repo behavior.

------------------------------------------------------------------------

# 33. How to Communicate Changes

The primary student/developer is still learning ML, finance, and parts
of the software stack.

When explaining work: - use simple language - explain what was changed -
explain why it was needed - mention files changed - mention commands to
run - mention expected output - identify risks/limitations - distinguish
required fixes from optional improvements

For complex ML concepts, explain the concept before presenting large
amounts of code.

------------------------------------------------------------------------

# 34. Academic Integrity / Claims

This is an academic FYP.

Never create fake: - model accuracy - F1 scores - backtest performance -
Shariah compliance results - dataset coverage - experiments -
citations - financial values

Only report results actually produced by code/data.

Document limitations rather than hiding them.

------------------------------------------------------------------------

# 35. Decisions and conflicts still requiring review

1. Experiment v1.1 uses 50 companies plus SPY, Alpaca SIP, 2016-2025 and early-2016 warm-up; original v1 used 40 companies including APD rather than LIN, Yahoo and 2015 warm-up. Preserve the original reference and record approval or further amendment; proposed is not approved.
2. Proposed screening profile HALALIFY_ASSET_ENTRY_V1 references MSCI Islamic Index Series May 2025 asset-entry rules: debt/assets <=0.30, (cash+interest-bearing securities)/assets <=0.30, (receivables+cash)/assets <=0.46, plus exact business/prohibited-income rules. These are proposed thresholds, not approved implementation or official index replication. SRS mentions AAOIFI as an example; it does not choose MSCI or AAOIFI rules. Obtain documented domain review and exact income definitions.
3. Proposed freshness controls: financial evidence <=180 calendar days and activity disclosures <=450 days. These are Halalify controls, not asserted religious-standard limits. Missing/ambiguous evidence stays unknown. Statuses: compliant, non_compliant, needs_review, insufficient_data. Only complete fresh passing evidence under a reviewed profile permits portfolio eligibility; a known failure can reject despite other missing evidence.
4. Financial mapping/TTM/issuer identity and corporate-action completeness remain unresolved. Do not assume company-level presence proves every period is covered.
5. SRS FR-8.2 suggests user-dependent classification thresholds; experiment preserves fixed labels with preference-dependent portfolios. Resolve explicitly rather than claiming the SRS changed.
6. Plan says monthly rebalance; experiment proposes every 20 exchange sessions. Proposed execution is next-session close, max ten holdings, 15% position cap, 30% study-group cap, at least eight selections or cash, uninvested cash at zero return, no shorts/leverage, 10 bps one-way trading costs with 0/25 bps sensitivity. Ranking p(return_high)-p(return_low) is not percentage expected return. Proposed moderate high-risk probability cap .50, conservative .20, aggressive none. These remain proposed strategy assumptions; document final approval.
7. SRS expected percentage-return display is not delivered by class probabilities. A numerical return estimate requires separately evaluated output/method.
8. Backend low/medium/high risk preference needs an explicit mapping to conservative/moderate/aggressive. standard/strict screening onboarding is not two approved screening standards.
9. Daily research, scheduled ingestion, inference freshness, dashboard refresh and portfolio rebalance are distinct cadences. Performance targets are requirements, not measured achievements.
10. Local explanation of individual predictions is not established by aggregate permutation importance alone. Define/validate a faithful explanation method.
11. Universe bias, delisted/missing securities, deployment, provider licensing and backend contracts remain documented limitations or decisions. Do not contact people, merge or deploy simply because a planning document lists those steps.

# 36. Most Important Rules to Remember

If only a few rules are retained, retain these:

**Rule 1:** HalalifyAI initially targets U.S. equities.

**Rule 2:** Return/risk ML prediction and Shariah screening are
separate.

**Rule 3:** Final portfolio holdings must pass the approved Shariah
screen.

**Rule 4:** Never use information before it was historically available.

**Rule 5:** SEC fundamentals must respect filing dates.

**Rule 6:** Train/validation/test must be chronological.

**Rule 7:** Label thresholds must be derived from training data only.

**Rule 8:** Distinguish superseded IEX history from verified SIP snapshots; do not claim complete 2015 coverage or global adjustment verification.

**Rule 9:** Do not invent Shariah rules or experimental results.

**Rule 10:** Risk preference should normally affect portfolio
construction rather than redefine ML class meanings.

**Rule 11:** Validate data before training models.

**Rule 12:** Keep raw source data immutable and keep secrets out of Git.

------------------------------------------------------------------------

# 37. First Action for Codex

Whenever starting a new task in this repository:

1.  Read this `AGENTS.md`.
2.  Inspect the current repository tree and relevant README/docs.
3.  Inspect the existing implementation before assuming a component is
    missing.
4.  Check the current Git branch/status.
5.  State what you found and what files you intend to change.
6.  For major or ambiguous design decisions, ask before implementing.
7.  For routine, clearly specified changes, implement them with
    tests/validation.

This file reflects the current project understanding and should be
updated when the team/supervisor makes a new authoritative decision.

# 38. Handoff status and required project layout (2026-10-02)

This replaces earlier stale snapshot guidance. Read the attached SRS and implementation plan plus docs/experiment_design.md v1.1, docs/data_dictionary.md v1.1 and docs/data_reconciliation.md. A context file cannot replace their detailed requirements or prove approval.

| Folder | Purpose |
| --- | --- |
| configs/ | Versioned settings and screening rules |
| data/raw/ | Immutable provider inputs and retrieval metadata; ignored by Git |
| data/interim/ | Extracted/cleaned intermediate evidence; ignored by Git |
| data/processed/ | Validated model-ready feature/label datasets; ignored by Git |
| data/samples/ | Small safe fixtures committed for testing |
| docs/ | Methodology, dictionary and contracts |
| notebooks/ | Exploration only |
| reports/ | Metrics, charts and validation reports |
| src/api/ | FastAPI service |
| src/data/ | Loading, collection, validation and cleaning |
| src/screening/ | Separate screening engine |
| src/features/ | Feature generation |
| src/labels/ | Future targets, classes and splits |
| src/models/ | Training and inference |
| src/evaluation/ | Evaluation and report generation |
| src/optimization/ | Portfolio construction/backtesting |
| tests/ | Automated tests |
| artifacts/ | Generated model files; ignored by Git |

Validation reports belong in reports/validation, not data/reports or data/interim/validation. Workspace outputs is a chat-transfer location, not an alternative project structure. Create missing folders when implementing their components. Preserve originals and update dependent paths before moving data.

New/changed files to read:
- configs/universe.json: exact 50 companies plus separate benchmark.
- src/data/reconciliation.py: shared universe, snapshot IDs and hashing helpers.
- src/data/collect_price_bases.py: versioned SIP split/all requests and normalized prices.
- src/data/collect_action_evidence.py: preserved corporate-action evidence.
- src/data/verify_action_pilot.py: limited AAPL split/dividend verification.
- src/data/collect_sec_snapshot.py: versioned CompanyFacts/submissions and scoped XOM predecessor retrieval.
- src/data/prepare_sec.py: expanded candidate extraction, next-session availability and quarantine.
- src/data/audit_reconciled_prices.py: price/calendar coverage audit, with readiness gates.
- src/data/download_alpaca.py, download_sec.py, download_spy.py: entry points to versioned collectors.
- src/data/extract_sec_fundamentals.py: legacy extraction now directed to interim; prepare_sec is the expanded evidence route.
- src/data/validate_data.py: legacy input audit with reports/validation default; not a universal audit of new schemas.
- tests/test_data_reconciliation.py: meaningful reconciliation tests; existing health test retained.
- README, AGENTS, requirements and .env.example: updated usage/context/dependencies/variable template.

Observed verification: 15 tests passed, including health, with one upstream Starlette/httpx deprecation warning. Environment: Python 3.12, pandas 3.0.1, NumPy 2.3.5 and isolated testing dependencies. Full pinned requirements were not independently installed/reproduced in a fresh environment. Basic/calendar scope found zero missing/unexpected price sessions. AAPL 2016-02-04 cash dividend and 2020-08-31 4:1 split pilot passed recorded tolerances. Do not generalize pilot results to all securities or all action types.

Not yet produced: validated 16-feature matrix, completed future labels/split manifests, fitted thresholds, trained return/risk models, model metrics, reviewed financial totals/TTM snapshots, approved screening verdicts, historical compliant portfolios/backtests, local explanations or integrated AI endpoints beyond the scaffold. training_ready=false and screening_ready=false.

Share datasets separately through authorized file transfer. No API credentials are needed by a teammate just to read retained files. Fresh downloads require their authorized credentials in local .env and a valid SEC identifying User-Agent; never send secrets in this handoff.

Transfer packages supplied earlier:
- Halalify-data-reconciliation.patch: code commit applied by git am.
- Halalify-reconciliation-code.zip: changed code/docs/configuration and patch.
- Halalify-reconciled-data.zip: newly collected raw inputs and interim outputs; not the complete original 50-company SEC archive.

Canonical delivered snapshots, relative to project root after extraction:
- data/raw/alpaca/alpaca_sip_20261001T192530002523Z/
- data/interim/prices/alpaca_sip_20261001T192530002523Z/daily_prices.csv
- data/raw/actions/20261001T193109154154Z/
- data/raw/sec_snapshots/20261001T193114591987Z/ (XOM predecessor)
- data/raw/sec_snapshots/20261001T193734106748Z/ (BAC identity evidence)
- data/interim/sec/sec_evidence_20261001T195303920031Z/financial_facts.csv
- data/interim/sec/sec_evidence_20261001T195303920031Z/quarantined_facts.csv
- reports/validation/reconciliation/: committed selected summaries and coverage.

These timestamped datasets were generated in the isolated checkout; their presence in each recipient's project must be checked. Earlier generated SEC runs may also exist; use the named latest run rather than concatenating runs blindly. Missing raw archives must be transferred or reproducibly collected before rerunning preparation requiring them.

Model selection reference: seed 42; 11 configurations per target. LR C=[0.1,1,10], StandardScaler, lbfgs, max_iter=2000. RF 300 trees, max_features=sqrt, depth=[6,12], min_samples_leaf=[20,50]. HGB learning_rate=.05, min_samples_leaf=30, l2_regularization=1, early_stopping=False, max_leaf_nodes=[7,15], max_iter=[100,200]. Select separately by validation macro-F1; differences below .01 use the proposed simplicity tie-break LR then RF then HGB. Record class-frequency and historical return/volatility baselines, confusion matrices, class/year/ticker/group metrics, probability calibration/log loss where appropriate. Non-overlapping anchors and synchronized 20-session moving-block bootstrap (1,000 replicates, 60-session sensitivity) are proposed uncertainty checks, not completed results.

Required maintained documents: README, experiment design, data dictionary, screening methodology, experiment log, evaluation report, model card, API contract and backtesting report. Their existence is not evidence of completion. Required backend agreement covers identity/ticker history, price/action/version schemas, missing values, ownership/refresh, model outputs and statuses, authentication/timeouts and persistence.

SRS covers data acquisition, features, classifiers, screening, portfolios, backtesting, explanations, risk preferences and dashboard. Targets include scheduled fetch/process within 60 seconds, dashboard within 3 seconds, full-universe classification within 10 seconds and risk selection within 30 seconds. These have not been measured. Retries/cache, security, resilience, modular tests and deployment reproducibility remain requirements. The plan names a Next.js/TypeScript frontend repository FYP, but its URL/code has not been reviewed.

Beginner terminology: a ticker is a market symbol; SPY is an ETF market reference, not one of the 50 company candidates; a CIK identifies a SEC filer; a session is an exchange trading day; a feature is known input; a target is a later observed answer; leakage means using information from the future; quarantine preserves questionable records outside accepted inputs; REVIEW means unresolved interpretation, not automatic failure or automatic approval.

Before continuing: check current branch/status and live remote branches, read current relevant source and documents, verify datasets and versions, identify the planned folder and tests, and make a focused change. Record actual evidence and remaining limitations. Never claim exact shared conversational memory: this file and its companion documents provide the transferable project context.

# Current execution override — 2026-10-02

Read `docs/data_readiness.md`, `docs/evaluation_report.md` and `docs/screening_methodology.md` before relying on older status statements in this file. The user explicitly confirmed that no Shariah standard/edition has been selected. Never turn the proposed MSCI example into an approved rule or interpret missing evidence as zero.

The isolated `feature/data-readiness` work integrates the published reconciliation/BAC changes and implements audited price-based features/targets and provisional train/validation comparisons. It is not merged into develop and has no peer approval. BAC issuer identity was checked against original filings; preserve the original source name and evidence. Five unsupported spin-off transitions remain excluded from model windows; no universal action certification exists.

118,643 usable price-based research rows are split into 58,157 training, 24,150 validation and 36,336 untouched-test rows. Sixteen features and future 20-session labels follow the reconciled dictionary. Test performance, final refit/calibration, screening, API integration and portfolio backtesting remain pending. Do not claim every mismatch or milestone is complete. This research does not approve the proposed source/universe/warm-up/class/cadence amendments.
