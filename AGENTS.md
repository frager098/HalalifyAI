# HalalifyAI --- Codex Project Context

## Purpose of this file

This file gives Codex the working context, technical decisions, data
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

Frontend â†’ HalalifyAPI (Node/Express application backend) â†’ HalalifyAI
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
start originally: approximately 2016 - Actual Alpaca dataset currently
has different coverage; see data section. - Prediction horizon: 20
future trading days - Return classes: Low / Medium / High - Risk
classes: Low / Medium / High - Planned portfolio rebalancing: monthly -
No intraday trading - No live brokerage execution - Deep learning is not
required for the initial prototype.

------------------------------------------------------------------------

# 5. Data Source 1 --- Alpaca Market Data

Purpose: Historical stock-price and volume behavior.

Current main file: `data/raw/alpaca_historical_prices.csv`

Expected columns: - date - ticker - open - high - low - close - volume

The downloader was configured approximately as: - timeframe = 1Day -
feed = IEX - adjustment = all - pagination enabled - requested start =
2016-01-01 - requested end = 2026-09-28

## Actual downloaded dataset facts

The currently reviewed Alpaca output contains: - 77,455 data rows - 50
stocks - 7 columns - date, ticker, open, high, low, close, volume - no
missing values were found in those seven columns during the reviewed
analysis

Most tickers begin around 2020-07-27 and continue through 2026-09-28.

CSCO was observed with earlier coverage beginning around 2018-05-22.

Important: The script requested 2016 onward, but the actual downloaded
dataset does NOT provide complete 2016-onward coverage.

Never claim that the project currently has ten years of Alpaca history
merely because 2016 was requested.

Investigate and document the coverage difference before training/final
reporting.

## Alpaca limitation

The free/basic IEX feed is not the consolidated SIP feed.

Therefore volume and possibly market coverage should not be presented as
consolidated whole-market data. Document this limitation in
research/reporting.

## Corporate actions

The downloader uses: `adjustment="all"`

Maintain a consistent interpretation of adjusted historical
prices/corporate actions throughout feature engineering and backtesting.

------------------------------------------------------------------------

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

# 7. Current Extracted SEC Dataset

Current long-format schema:

`ticker,company_name,field,sec_concept,value,unit,period_start,period_end,filing_date,form,fiscal_year,fiscal_period,accession_number`

Reviewed dataset facts: - 39,092 rows - 50 unique stocks/companies -
earliest filing date: 2009-05-07 - latest filing date: 2026-09-22 -
earliest financial period end: 2006-09-30 - latest financial period end:
2026-08-31 - 10-Q rows: 28,466 - 10-K rows: 10,626

Current normalized financial fields and row counts: - Cash: 14,990 -
Total Assets: 7,062 - Revenue: 6,481 - Total Debt: 6,102 - Accounts
Receivable: 4,457

Company coverage: - Cash: 50/50 - Total Assets: 50/50 - Total Debt:
41/50 - Revenue: 40/50 - Accounts Receivable: 36/50

These gaps do not automatically mean downloads failed. They may result
from incomplete XBRL concept mapping or issuer-specific reporting
differences.

------------------------------------------------------------------------

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

# 10. Critical Point-in-Time / Leakage Rule

This is one of the most important rules in the project.

Never use a company's financial information at a historical ML date
before that information had actually been filed/publicly available.

Example:

Financial period ends: 2024-03-31

Company files its 10-Q: 2024-05-01

A model prediction made on: 2024-04-15

MUST NOT use that filing.

The model could not have known it yet.

Therefore SEC fundamentals must be joined to market dates according to
information availability, primarily `filing_date`, not merely
`period_end`.

For a market date t, use only financial information whose filing date is
\<= t.

This prevents look-ahead/data leakage.

------------------------------------------------------------------------

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

# 13. Planned Market Features

Initial feature groups:

## Returns

-   1-day return
-   5-day return
-   20-day return
-   60-day return

Return is a percentage/rate of price change, not the stock price itself.

## Momentum

Initial windows: - 20-day momentum - 60-day momentum

Momentum describes the direction/strength of price movement over a
selected historical window.

It is not the same as volatility.

## Trend

-   20-day moving average
-   50-day moving average
-   price / MA20 ratio
-   price / MA50 ratio

## Risk

-   20-day volatility
-   60-day volatility
-   trailing maximum drawdown

Volatility measures how much returns fluctuate.

## Liquidity/activity

-   average volume
-   recent volume change

All features for date t must use only information available at or before
t.

------------------------------------------------------------------------

# 14. Planned Fundamental Features

Initial plan included: - debt ratio - cash ratio - revenue growth -
profit margin - market capitalization

However, the current extracted SEC data does not yet fully support all
of these.

Important gaps: - Profit margin needs net income and revenue. Current
extraction does not yet include net income. - Historical market cap
requires point-in-time shares outstanding Ã— historical price, or another
defensible historical source. - Sector/industry are not straightforward
Company Facts fields. - Some debt/revenue/receivable coverage is
incomplete.

Do not fabricate missing features.

Either: 1. extend the SEC extraction with correctly validated
concepts/data, or 2. revise the feature set transparently with
documented justification.

------------------------------------------------------------------------

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

# 17. Train / Validation / Test Split

Financial time-series data must be split chronologically.

Never randomly shuffle historical rows across train/test in a way that
allows future information to influence past training.

Concept:

Past â†’ Train â†’ Validation â†’ Test â†’ Future

Do not use:

Random mixture of 2020--2026 rows across all sets.

Also ensure rolling features and fundamental joins do not leak future
information.

------------------------------------------------------------------------

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

# 29. Git Workflow Context

The shared repository has used a `develop` branch.

Typical collaborator workflow:

``` bash
git checkout develop
git pull origin develop
# make changes
git add <intended files>
git commit -m "meaningful message"
git push origin develop
```

Before pushing: - inspect `git status` - ensure no secrets - ensure no
huge unintended datasets - ensure generated files/caches are not
accidentally staged

Do not force-push shared branches unless explicitly instructed and the
consequences are understood.

------------------------------------------------------------------------

# 30. Data Joining Direction

Eventually Alpaca and SEC data need to become an ML-ready point-in-time
dataset.

Conceptual example:

`market date + ticker + market features + latest legally available fundamental features`

For each `(ticker, market_date)`: - calculate market features using data
\<= market_date - find appropriate SEC facts whose filing_date \<=
market_date - never use future filings - preserve provenance where
practical

The raw SEC long format should not simply be joined directly to every
market row without resolving: - concept mappings - filing versions -
fiscal periods - duration vs instant facts - duplicates -
amendments/restatements - missingness - units

Build and test this pipeline carefully.

------------------------------------------------------------------------

# 31. Recommended Development Order

Unless current repo state shows that some steps are already completed,
prefer this order:

1.  Inspect current repository and documentation.
2.  Validate raw Alpaca dataset.
3.  Validate SEC extraction and XBRL mappings.
4.  Build clean/interim point-in-time fundamentals.
5.  Build market features.
6.  Join market and fundamentals without leakage.
7.  Create 20-day return/risk targets.
8.  Perform chronological train/validation/test split.
9.  Calculate classification thresholds from training data only.
10. Train baseline models.
11. Evaluate and compare models.
12. Implement/version Shariah methodology after rules are formally
    selected.
13. Build portfolio optimization.
14. Build historical backtesting.
15. Add explainability.
16. Expose stable AI functionality through FastAPI.
17. Integrate with HalalifyAPI/frontend.

Do not jump directly to sophisticated models before validating the data.

------------------------------------------------------------------------

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

# 35. Important Unresolved Decisions

Do not silently decide these:

1.  Exact Shariah standard/version.
2.  Exact Shariah financial ratios and thresholds.
3.  Treatment of special industries/business activity.
4.  Final historical universe selection methodology.
5.  Resolution of Alpaca's requested-vs-actual historical coverage.
6.  Final SEC concept mappings for all 50 issuers.
7.  How to calculate historical market capitalization.
8.  Whether/how to add net income for profit margin.
9.  Final Low/Medium/High threshold methodology.
10. Exact portfolio objective and risk-preference mapping.
11. Final rebalance rules and transaction-cost assumptions.
12. Handling of delistings/universe changes and survivorship bias.
13. Production deployment architecture.

When one of these becomes necessary, present the alternatives and
request/record the decision rather than guessing.

------------------------------------------------------------------------

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

**Rule 8:** Do not claim 2016 Alpaca coverage when the actual current
dataset mostly begins in 2020.

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

# 38. Data reconciliation update 2026-10-02

Earlier IEX coverage notes above describe an old snapshot. Reviewed current local SIP files have 134,237 rows (50 companies) through 2026-09-28, with 49 starting 2016-01-04 and LIN starting 2018-10-31. A new fixed-study 2016-2025 collection contains the companies plus separate SPY and separate split/all price bases. Use docs/experiment_design.md and docs/data_dictionary.md v1.1 together with docs/data_reconciliation.md for the proposed revision; do not claim review approvals. Preserve originals, timestamp new snapshots, put intermediate datasets in data/interim and reports in reports/validation. Run task changes through focused feature branches and peer-reviewed PRs into develop, overriding the old direct-to-develop workflow example. The dictionary uses next-session-after-filing availability, stricter than the older <= filing-date example. No missing screening values become zero; no total-debt/TTM snapshot is certified by candidate extraction. No trained model or portfolio is created by this change.
