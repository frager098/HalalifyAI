# Missing-field recovery and rerun

Same information cutoff: **31 December 2025**. SEC API snapshots were retrieved on 20 October 2026 and cross-checked to eligible original filings, never used as current historical truth.

All 50 CompanyFacts downloads succeeded. 12,482 eligible original fact representations matched exactly on concept, accession, period and value.

| Result | Before | After |
| --- | ---: | ---: |
| Complete evidenced pass | 0 | 0 |
| Fails an initial filter | 16 | 19 |
| Needs further evidence | 34 | 31 |

## What was actually recovered

- Source-bound borrowing components, including Lowe's unsecured notes explicitly excluding finance leases.
- Receivable values previously rejected because detailed notes and rounded narrative used different precision. Declared XBRL rounding intervals must intersect; real conflicts stay unknown.
- Interest-bearing security balances, with cash overlap handled explicitly. Apple's table requires a subtraction before adding cash; NVIDIA's reported securities floor is sufficient without adding cash.
- Separate annual interest income from original report tables for Costco and McDonald's, and additional eligible gross-interest concept candidates.
- Microsoft's combined interest/dividend figure is retained as combined. Net interest and income mixed with other items remain separate candidates, not invented gross income.

Field-coverage counts are amounts/candidates found, not proof of complete categories:

```json
{
  "assets_found": 50,
  "debt_amount_found": 49,
  "cash_amount_found": 50,
  "receivable_amount_found": 47,
  "annual_revenue_candidate_found": 48,
  "gross_interest_candidate_found": 33,
  "complete_prohibited_income": 0
}
```

## What remains unavailable or unresolved

**All required fields are not complete.** Some companies do not separately disclose the business/product shares needed for the prohibited-revenue test. Other income is net or combined. An absence in CompanyFacts does not prove absence in a report; the full original annual and latest financial notes were inventoried too. These searches still do not establish every prohibited-income numerator. No absent disclosure was converted to zero.

The 31 review cases are not halal or haram verdicts. Full source mapping and appropriate review remain necessary before a complete pass or portfolio eligibility. Original/raw data and prediction training data were not altered.

| Company | Current result | New result? | Gross-interest candidate found? |
| --- | --- | --- | --- |
| AAPL | fails_initial_filters | yes | not established |
| MSFT | needs_review | no | not established |
| NVDA | fails_initial_filters | yes | yes |
| AMD | needs_review | no | not established |
| AVGO | fails_initial_filters | no | yes |
| ORCL | fails_initial_filters | no | yes |
| ADBE | needs_review | no | yes |
| CRM | needs_review | no | yes |
| CSCO | needs_review | no | not established |
| INTC | needs_review | no | yes |
| GOOGL | needs_review | no | yes |
| META | needs_review | no | yes |
| NFLX | needs_review | no | yes |
| AMZN | needs_review | no | yes |
| TSLA | needs_review | no | yes |
| HD | fails_initial_filters | no | not established |
| LOW | fails_initial_filters | yes | not established |
| NKE | needs_review | no | yes |
| SBUX | fails_initial_filters | no | not established |
| MCD | fails_initial_filters | no | yes |
| COST | needs_review | no | yes |
| WMT | needs_review | no | yes |
| JNJ | needs_review | no | yes |
| LLY | fails_initial_filters | no | yes |
| ABBV | needs_review | no | not established |
| MRK | needs_review | no | yes |
| TMO | fails_initial_filters | no | yes |
| ABT | needs_review | no | yes |
| DHR | needs_review | no | yes |
| CAT | needs_review | no | not established |
| DE | fails_initial_filters | no | not established |
| HON | fails_initial_filters | no | yes |
| UPS | fails_initial_filters | no | not established |
| UNP | needs_review | no | yes |
| GE | needs_review | no | yes |
| XOM | needs_review | no | not established |
| CVX | needs_review | no | not established |
| COP | needs_review | no | yes |
| SLB | needs_review | no | yes |
| JPM | fails_initial_filters | no | yes |
| BAC | fails_initial_filters | no | yes |
| GS | fails_initial_filters | no | yes |
| MS | fails_initial_filters | no | yes |
| V | needs_review | no | not established |
| MA | fails_initial_filters | no | not established |
| PG | needs_review | no | yes |
| KO | needs_review | no | yes |
| PEP | needs_review | no | not established |
| LIN | needs_review | no | yes |
| NEE | fails_initial_filters | no | not established |
