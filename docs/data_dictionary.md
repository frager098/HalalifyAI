# Screening data dictionary

Scope: screening profile V3, implemented 20 October 2026. This documents screening inputs/outputs; the teammate's existing modeling data schema is documented separately in `MODELING_WORKSPACE.md` and has not been redefined here.

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
