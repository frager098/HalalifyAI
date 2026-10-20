# Halalify screening methodology

Implemented and source-checked on 20 October 2026. Profile:
`HALALIFY_FTSE_YASAAR_INITIAL_RESEARCH_V4` (the same-day V3 run is retained in Git history).

## What is authentic, and what is implemented

The authoritative public reference is [FTSE Yasaar Global Equity Shariah Index Series, v4.6, February 2026](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-yasaar-global-equity-shariah-index-series-ground-rules.pdf), sections 4.3.1 and 4.3.2. Its public thresholds fit an asset-based US-stock research prototype. They are not interchangeable with AAOIFI, MSCI, PSX/KMI or FTSE IdealRatings rules.

The documentation and code reproduce these public initial-entry thresholds. They do **not** perfectly reproduce the full FTSE/Yasaar process. Section 2.4.1 describes proprietary screening and Yasaar board review. Index membership, ongoing quarterly monitoring, the two-quarter buffer, official review timing and dividend purification are not implemented. No official Yasaar decision or religious certification is claimed. The user authorized this research implementation and direct develop push; supervisor/domain and peer approval have not been invented.

## Public rules applied

| Check | Numerator / denominator | Passing comparison |
| --- | --- | --- |
| Debt | Debt / total assets | strictly below 33.333% |
| Cash and interest-bearing items | Cash plus interest-bearing items / total assets | strictly below 33.333% |
| Receivables and cash | Accounts receivable plus cash / total assets | strictly below 50% |
| Income | Gross interest plus non-compliant activities income / total revenue | at most 5% |
| Business activities | Non-permitted business revenue / total revenue | at most 5% |

Public activity categories cover conventional finance, alcohol/intoxicants, pork/non-halal food, specified entertainment, tobacco/cannabis and weapons/defence. The public list is not exhaustive. Words appearing in a company report are search clues, not proof of a prohibited revenue share. Net interest after expenses cannot replace gross interest. Unallocated investment income and ordinary sales revenue do not automatically establish the required full numerator and denominator.

Exact decimal arithmetic is used before any display rounding. Equality fails the first three exclusive limits and is allowed at the 5% income/business limits. No ratio is calculated with missing, nonfinite, negative or zero denominator data. There is an independently callable/tested function per rule in `src/screening/yasaar.py`.

## Data and date policy

The run uses all 50 existing company candidates from `configs/screening_universe.json`. SPY is a market reference and is excluded. No companies are silently replaced.

Evidence cutoff is **31 December 2025**, using the original retained 2015-2025 SEC archive. Applying the 2026 rule version to that snapshot is an explicit retrospective research choice, not a claim that this edition was in force in 2025. It is also not a current October 2026 screen. A current result requires newer reports and a new reviewed snapshot.

The source archive, extracted business evidence and numeric candidates must match the SHA-256 hashes in `configs/yasaar_research.json`; different inputs stop the run. Each selected original report is checked again against its archive hash. Financial facts require the exact issuer CIK, USD, consolidated non-dimensional context and reporting date. Segments and other issuers are excluded from balance-sheet totals. Available amendments for the selected or later period block a decision pending review. Only information available from the next exchange session after filing/acceptance is used.

The latest eligible complete financial filing provides balance-sheet observations. The latest eligible annual filing provides business excerpts and annual income candidates. Annual income diagnostics and quarterly balance-sheet figures remain separate; periods are never silently mixed into one ratio. Financial age over 180 calendar days or business disclosure age over 450 days blocks a decision. These age controls are project policy, not FTSE thresholds.

## Partial amounts and missing information

The current source adapter establishes conservative **minimum amounts**, rather than pretending every financial category is complete. It chooses a reported debt total or explicitly disjoint current/noncurrent components; totals are never added to overlapping components. Mixed debt/finance-lease figures are not counted automatically. A documented finance-lease subtraction may establish a debt floor, with conflicts blocked. One explicit Deere custom-concept mapping retains issuer, namespace, source label and rationale in the versioned configuration.

A minimum amount that already breaches a ceiling is sufficient for an initial research failure. A minimum below the ceiling cannot prove a pass. Cash alone does not prove the cash-plus-interest-bearing-items total; a receivable observation does not prove all relevant receivables were collected. Missing income is unknown, never zero.

JPM, BAC, GS and MS have source-specific research activity assessments based on principal conventional-financial-service segments in the original annual business disclosures. No numerical percentage was invented. Those interpretations remain distinct from domain approval. NFLX's streaming business is flagged for interpretation rather than automatically assigned a prohibited percentage. Other companies need product/segment and complete income review; absence of a flagged word is not a clearance.

## Results and portfolio safety

`passes_research_filters` requires all four financial checks and the business check to pass with complete reviewed amounts. `fails_initial_filters` means at least one evidenced initial filter fails. `needs_review` means the available information cannot support a decision or a blocking amendment/stale source exists. The engine can pass a complete packet; the synthetic test fixture proves this without inventing real-company data. The retained-source adapter cannot assert completeness from tag presence alone.

`portfolio_eligible` requires a complete research pass **and** the configured domain approval. All 50 flags are false in this run. This enforces the SRS FR-4.1/4.2 calculations and FR-4.4/FR-5.1 exclusion boundary at the result layer. Dashboard display, optimizer integration and approved production eligibility are not claimed complete.

## V4 missing-field recovery

The follow-up user request authorized further source/API exploration without another branch. All 50 new SEC CompanyFacts requests succeeded. Each current response is preserved with issuer, URL, retrieval time and checksum. It is supplementary evidence: matching uses the exact original accession, period and value and excludes future filings; current or restated API values never overwrite the original historical reports. The source archive's latest eligible financial and annual reports were re-inventoried with custom and dimensional contexts retained as candidates.

For balance decisions, only standard concepts and specifically permitted debt-instrument/type contexts can add a lower bound. Business-segment and fair-value-measurement contexts are not silently consolidated. Rounded and detailed observations may be reconciled only when their explicitly declared XBRL precision intervals intersect; incompatible values remain unknown. A broad custom tag is not approved merely because its local name resembles US-GAAP.

Debt-securities observations may strengthen the cash/items lower bound, but cash and securities are not blindly added because cash equivalents can occur in both. Apple's original classification table supports an explicit source-bound overlap subtraction before adding cash. The resulting initial cash/items diagnostic is 36.6233% of assets. NVIDIA's reported securities subtotal alone is 34.1003%; no extra cash is added. Lowe's original note explicitly excludes finance leases from its unsecured-note carrying amount; that component alone is 70.1813% of assets. These three source-backed findings change the count from 16 to 19 initial-filter failures.

Source-bound original annual table mappings recover Costco's USD469 million and McDonald's USD103 million interest-income candidates. McDonald's displays that income as an offset to interest expense; its positive income amount is preserved. Microsoft's USD2,647 million remains **combined interest and dividends**, not a fabricated separate gross-interest figure. Income candidates do not clear the full prohibited-income test or establish prohibited business revenue as zero. All three reviewed mappings bind exact issuer, accession, source hash, row cells, scale and annual period.

Additional retained inputs are `data/raw/screening_recovery_20261020/companyfacts/` and `data/interim/screening/recovery_notes_20261020/`. Their manifest hashes and the source-specific mapping hash are registered in the V4 profile. Reproduction requires these exact retained files in addition to the original archive and extracted candidate set; a later fresh API download can differ and requires a new reviewed registration. Completed collection reuse verifies every retained file and does not rewrite its original metadata. See [screening_field_recovery_20261020.md](screening_field_recovery_20261020.md) for the limitations and collection commands.

## Reproduce

Install `requirements.txt` and `requirements-screening.txt` in Python 3.12. From the repository root, with the separately shared retained evidence installed:

```bash
python -m src.screening.run_yasaar --repo . --archive data/raw/sec_screening_evidence/sec_sources_20261002.zip --evidence data/interim/screening_evidence/sec_2015_2025_v2
python -m pytest -q
```

Reports are in `reports/screening/ftse_yasaar_2025/`: readable Markdown/HTML, per-stock CSV, full selected evidence JSON, field coverage and specific remaining-review tasks. Intermediate source candidate inventories stay in ignored `data/interim/screening/`. Raw files remain immutable and ignored. The original SEC archive and extracted candidate files are shared separately; a Git pull installs code/reports, not those large inputs.

See [screening_results_20261020.md](screening_results_20261020.md) for the executed counts and [data_dictionary.md](data_dictionary.md) for result fields. The plan layout is followed: configs, src/data, src/screening, data/samples, tests, docs and reports. The user explicitly requested this task on existing `develop` without another branch; the usual feature-branch workflow is overridden for this task only.


## Latest follow-up — 20 October 2026

Read [data_completion_20261020.md](data_completion_20261020.md) for the executed source search and price rebuild. V5 screening is 0 complete passes / 20 failures / 30 reviews, with 37 gross-interest candidates. Earlier V4 counts and claims that the training notebook was unchanged apply only to that earlier task. The new 118,643-row price research dataset and repaired notebook are separate from screening. No full Colab model fit, higher accuracy, live screening API, domain approval or portfolio backtest is claimed.
