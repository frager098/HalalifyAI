# BAC company identity resolution

Reviewed 2026-10-02. Task branch: `feature/bac-identity-verification`, based on updated `develop` at `255436b`. The earlier reconciliation feature provides the input dataset; it is not assumed merged.

## Finding

BAC is Bank of America Corporation, SEC CIK `0000070858`. The preserved CompanyFacts response labels it `BofA Finance LLC`; the submissions response identifies `BANK OF AMERICA CORP /DE/` and lists BAC. A source display-name disagreement alone does not establish that the numbers describe the wrong entity.

The verification checks each accession referenced by BAC's 1,115 retained candidate facts. All 69 original XBRL instances identify Bank of America Corporation (including the historical spelling `BANK OF AMERICA CORP /DE/`) and CIK 70858. All 1,115 records match their original filings exactly on US-GAAP concept, USD unit, start/end periods and numeric value, in a non-dimensional issuer context. Each candidate also matches the preserved CompanyFacts input on accession, form and filing date. No identity-unverified BAC record remains in this extracted input.

Example source: [Bank of America's 2024 annual-report filing](https://www.sec.gov/Archives/edgar/data/70858/000007085825000139/0000070858-25-000139-index.htm), filed 2025-02-25. Its [original XBRL instance](https://www.sec.gov/Archives/edgar/data/70858/000007085825000139/bac-20241231_htm.xml) contains the registrant identity and reported amounts.

This establishes identity for these facts. The exact cause of the API's top-level display label has not been established. Do not claim it is a different issuer's financial dataset, a proven SEC system bug, or that every concept in the complete CompanyFacts response has been audited.

## Correction and scope

The normalized `company_name` is `Bank of America Corporation` for verified rows. `source_company_name` retains `BofA Finance LLC`. Added metadata records identity verification and the original filing URL. Matched records have `statement_scope=non_dimensional_issuer_context_verified`.

The original JSON, original 77,075-row CSV, amounts, units, periods, filing dates, accession numbers, fact IDs, availability sessions and general `review_status` are preserved. Other companies are unchanged apart from blank newly added columns in the combined CSV. The 22 previously quarantined financial observations stay separately quarantined; this identity task does not rehabilitate them.

Output paths:

- `data/raw/sec_identity/bac_identity_20261002/`: 69 original filing indexes and XBRL instances, plus retrieval/source/hash metadata.
- `data/interim/sec_identity/bac_identity_20261002/BAC_identity_verified_financial_facts.csv`: 1,115 verified BAC candidate records.
- `data/interim/sec_identity/bac_identity_20261002/BAC_identity_needs_review.csv`: header-only, zero unresolved BAC identity records in this input.
- `data/interim/sec_identity/bac_identity_20261002/financial_facts_identity_updated.csv`: all 77,075 candidate records with BAC identity corrected.
- `reports/validation/bac_identity/bac_identity_20261002/bac_identity_resolution.json`: filing URLs, hashes, identities, counts and limits.

These are intermediate evidence files. They are not finalized debt totals, TTM financial snapshots, training features or compliance results. `review_status` stays unreviewed for financial mapping. Verification is scoped to the delivered input; fresh or different BAC facts must be verified again. Preserve historic filing availability even though verification was performed later.

## Reproduce

Use Python 3.11/3.12 with `requests` installed. No provider API key is required. Supply a legitimate SEC identifying User-Agent with your real contact. From the repository root:

```bash
python src/data/verify_bac_identity.py --companyfacts PATH_TO_BAC_companyfacts.json --submissions PATH_TO_BAC_submissions.json --financial-csv PATH_TO_financial_facts.csv --user-agent "HalalifyAI your-real-contact@example.com"
python -m unittest discover -s tests -p test_bac_identity.py -v
```

The default creates a new timestamped run. An explicit `--run` identifier permits resuming downloads from that run's preserved cache and regenerating its derived report/output. Do not edit cached provider files; choose a new run for fresh retrieval. Requests are sequential with spacing and bounded retries. Failures or unmatched observations stay in the separate needs-review output; they are not silently renamed.

Nine offline tests passed: verified/historical names, rejecting the subsidiary/wrong CIK, excluding segment contexts and invalid values, selecting the correct SEC instance link, rejecting external links, and preserving source/other-company records during normalization. Actual full-data verification found 69/69 filing identities and 1,115/1,115 facts matching. No fresh full-project dependency installation or model evaluation is claimed.

Code/tests/docs and the small report can be reviewed in a PR targeting develop. Raw/interim data remain ignored by Git and travel separately. No merge, push or screening approval has occurred as part of this task.
