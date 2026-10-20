# Screening data dictionary

Scope: screening profile V4, revised 20 October 2026 after the API/original-note recovery. This documents screening inputs/outputs; the teammate's existing modeling data schema is documented separately in `MODELING_WORKSPACE.md` and has not been redefined here.

| Field | Meaning |
| --- | --- |
| `ticker` | One of the 50 registered company symbols; SPY is excluded. |
| `cik` | SEC issuer identifier checked against the original XBRL context. |
| `as_of_date` | Information cutoff, fixed to 2025-12-31 for this run. |
| `reporting_date` | Date of the selected financial balance sheet. |
| `filing_date` | Date the selected report was filed. |
| `available_from_session` | First exchange session after the filing/acceptance date. |
| `source_url`, `source_sha256`, `accession_number` | Original filing provenance. |
| `checks.*.ratio` | Unrounded decimal fraction, stored as a string; `0.25` means 25%. Null means unknown. |
| `checks.*.minimum_amount` | Minimum evidenced USD amount; not automatically the complete category total. |
| `checks.*.components` | Exact concepts, values, contexts, labels and mappings supporting that amount. |
| `completeness` | `lower_bound_only` or an explicitly reviewed full total; never inferred from tag presence. |
| `research_status` | Complete research pass, initial filter failure or needs review. |
| `failed_checks` | Names of established failing filters; an empty list alone does not mean pass. |
| `missing_or_incomplete_checks` | Required categories still lacking full usable evidence. |
| `stale_evidence` | Whether project age controls block a decision. |
| `domain_approved` | Separate approval state; false for this implementation. |
| `portfolio_eligible` | True only for a fully evidenced pass with required approval; false for all 50 here. |

Income candidates preserve original units, annual start/end dates, issuer, dimensions, numeric transformation status, source hashes and availability. Revenue/interest diagnostics do not become final income ratios while full categories or denominator remain unestablished. Numeric zeros must be explicitly reported or supported by the XBRL transformation; missing observations are never zero-filled.

Inputs: immutable SEC ZIP in `data/raw/sec_screening_evidence/` and extracted candidates in `data/interim/screening_evidence/sec_2015_2025_v2/`, with exact hashes in the profile. Output CSV percentages are display values only; decisions use unrounded decimals in the JSON. Candidate inventories belong in ignored `data/interim/screening/`; selected evidence and audit reports belong in `reports/`.

V4 additionally retains 50 current SEC API snapshots and 50 original-note inventories, with exact manifest hashes. `reported_decimals`, `reported_values`, `lower_bound`, `upper_bound` and `rounding_reconciled` explain reconciliation of the same fiscal fact at different declared precision; they do not certify a complete financial category. `dimensions` remains explicit. Only specified instrument/type scopes can strengthen debt floors; product/segment contexts are not silently treated as consolidated totals.

`checks.income.recovered_interest_disclosures` distinguishes reported gross-interest candidates from net interest, combined interest/dividends and other combined/partial income. A matching report table can supply a reviewed positive earned-interest figure even when shown as an expense offset. A missing or combined observation never becomes zero or a complete prohibited-income numerator. `api_crosscheck.json` counts exact historical fact representations across financial/annual roles; the roles can overlap, so that count is not a claim of unique economic observations.


## Latest follow-up — 20 October 2026

Read [data_completion_20261020.md](data_completion_20261020.md) for the executed source search and price rebuild. V5 screening is 0 complete passes / 20 failures / 30 reviews, with 37 gross-interest candidates. Earlier V4 counts and claims that the training notebook was unchanged apply only to that earlier task. The new 118,643-row price research dataset and repaired notebook are separate from screening. No full Colab model fit, higher accuracy, live screening API, domain approval or portfolio backtest is claimed.

The price research table has 16 predictors defined in `src/features/core.py`; future return, volatility and excess return use sessions t+1 through t+20. The named source CSV and raw/adjusted price bases must pass `training_inputs`; SPY is separate. Store complete eligible rows in data/processed and full exclusion audit separately. Screening bounds/candidates in the financial ledger are not ML predictors or approved full totals.
