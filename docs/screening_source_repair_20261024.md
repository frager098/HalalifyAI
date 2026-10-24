# Free source screening repair

The new run checks the same 50 stocks using the same FTSE Yasaar research rules and information available by **31 December 2025**. The result is **22 rule failures, 28 undecided stocks and no complete passes**. This is a historical research screen, not a current-market result or religious certificate.

## What changed

| Repair | What the original report supports | What it does not prove |
| --- | --- | --- |
| Walmart revenue | Total revenue is USD680.985 billion; the earlier provisional selection was USD674.538 billion of sales. The original total now replaces that candidate and the earlier figure is retained for audit. | A complete prohibited-income or business assessment. |
| Chevron interest | The 2024 segment note reports USD296 million of interest in All Other. The exact original row and source are registered. | The complete company's interest or all prohibited income. |
| Caterpillar borrowing | A reported USD4.509 billion short-term borrowing component is recovered from the original September 2025 report. | Complete debt. It remains a partial amount below the debt limit. |
| Caterpillar combined income | USD482 million is recorded as investment and interest income together. | A separate pure-interest amount. |
| Caterpillar business | The user approved classifying the finance and insurance activity as conventional finance for this research run. Consolidated external Financial Products revenue is USD3.446 billion against USD64.809 billion total, approximately 5.317%, above the 5% limit. | Qualified Shariah approval. Internal finance revenue is excluded; the larger pre-elimination segment total is not used. |
| Decision code | A completed, source-checked income or business review can now flow through to a real pass or failure. Missing, draft, wrong-period and mismatched-source reviews cannot pass. | That a complete real-company review has already been supplied. The completed-review registry is currently empty. |

All 50 stocks now have at least one borrowing observation, up from 49. Gross-interest candidates or components increased from 37 to 38. Assets and cash observations remain 50; receivable observations 47; annual revenue candidates 48. A found amount is not automatically a complete total.

The new code separates missing observations, combined income, and unfinished category review. It does not misclassify ownership interests as earned interest. Source rounding is checked before a completed income or business review can clear the five-percent limit.

## What still needs work

The 28 undecided stocks still require completed business and income assessments. Some figures are available but need classification or a complete-category explanation; other breakdowns are not established by the reports checked. A broad sales category does not state the exact prohibited-product share. A combined or net income line does not provide every gross component.

The code repair does **not** justify replacing those gaps with zero. No real-company income check was marked complete merely to create a passing stock. Qualified interpretation or a dated specialist breakdown may still be needed. Paid data access and a change of standard have not been adopted.

## Files to read

- [All 50 results](../reports/screening/ftse_yasaar_2025_v7/results.md)
- [One source and gap row per stock](../reports/screening/ftse_yasaar_2025_v7/data_gaps.csv)
- [Detailed source-backed results](../reports/screening/ftse_yasaar_2025_v7/results.json)
- [Coverage counts](../reports/screening/ftse_yasaar_2025_v7/field_coverage.json)

The earlier `ftse_yasaar_2025` report and the V6 Word checklist remain the 21-failure/29-review baseline. The new V7 report is the latest repair result; previous outputs and downloaded reports are preserved.

## Reproduce

With the retained original source archive, extracted evidence and supplementary snapshots installed at their documented paths:

```bash
python -m src.screening.run_yasaar --repo . --archive data/raw/sec_screening_evidence/sec_sources_20261002.zip --evidence data/interim/screening_evidence/sec_2015_2025_v2 --out reports/screening/NEW_SCREENING_RUN
python -m src.screening.verify_results --repo . --report reports/screening/NEW_SCREENING_RUN/results.json
python -m pytest -q
```

Choose a new output folder: an existing versioned result is never overwritten. No model training, feature changes or price-data replacement is part of this repair.

Verification: all **117 software tests passed** in the existing isolated Python 3.12 environment and again from a fresh committed-source export using the user's Python 3.13 environment. Re-running the retained original sources in the fresh copy reproduced all 50 complete company records exactly; the independent result verifier also passed. This verifies the program and its saved results, not the completeness of the remaining company disclosures.

## Completed review contract

`configs/screening_evidence_reviews.json` accepts only source-bound completed research reviews. Each entry identifies ticker, SEC issuer number, original accession, URL and SHA256, annual period and next-session availability. Each completed check names its reviewer and explains full category coverage, disjoint amounts, gross income where relevant, and its total-revenue definition. Numeric references must resolve exactly to the original issuer's USD facts in the same annual period. Explicit source classifications and reasons are required; a boolean alone cannot replace the amounts or source review.

For business clearance, all classified revenue components must reconcile to consolidated revenue. A zero prohibited share can be derived only from that fully reviewed partition, not from absent keywords. For income, every supplied component must be source-resolvable; an absent amount cannot become an invented zero. Rounded observations that span the threshold remain undecided. Independent verification recomputes arithmetic, precision, periods and safety flags.

Source-specific **failure** findings remain in `configs/business_numeric_assessments.json`; these need only establish a prohibited category above the limit, not classify every other category. CAT's interpretation was explicitly authorized by the user on 24 October 2026. `domain_approved` and all portfolio eligibility flags remain false. No peer or religious approval is claimed.
