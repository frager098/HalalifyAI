# What was recovered, and what still cannot be decided

The user requested further field recovery, another screening run and a direct push to existing develop. The information cutoff remains **31 December 2025** so current 2026 figures are not mixed into the historical FYP screen.

## Actual work and results

All **50 SEC CompanyFacts API downloads succeeded**. The latest eligible original financial and annual reports for the same 50 companies were searched again, preserving custom tags, financial-instrument dimensions, relevant table rows and narrative findings. The API cross-check found **12,482 matching original fact representations** on concept, accession, period and value. Financial and annual roles can overlap; this is not a count of unique economic facts. API observations filed after the cutoff are excluded and never replace original 2025 evidence.

| Result | Before recovery | After recovery |
| --- | ---: | ---: |
| Complete evidenced research pass | 0 | 0 |
| Fails an initial filter | 16 | 19 |
| Needs further evidence | 34 | 31 |

Three results changed: **Apple and NVIDIA fail the cash/interest-bearing-items limit; Lowe's fails the debt limit**. Their original securities/debt notes supply the supporting amounts. Apple's cash overlap is explicitly subtracted; NVIDIA's securities subtotal is used alone; Lowe's selected borrowing component explicitly excludes finance leases. These are public-rule research findings, not official Yasaar approval or current-market verdicts.

Other extraction gaps were resolved too. Adobe and Cisco receivables had detailed amounts and rounded narrative versions; declared precision shows these representations are consistent. Costco's separate USD469 million and McDonald's USD103 million annual interest-income figures were recovered from original tables. Microsoft reports USD2,647 million interest **and dividends together**, which remains combined rather than being mislabeled as pure interest.

| Amount/candidate found | Before | After |
| --- | ---: | ---: |
| Assets | 50 | 50 |
| At least one usable borrowing amount | 48 | 49 |
| Cash | 50 | 50 |
| At least one receivable amount | 43 | 47 |
| Annual revenue candidate | 48 | 48 |
| Gross-interest candidate/component | 25 | 33 |
| Complete prohibited-income numerator | 0 | 0 |

**All required fields are still not complete.** A number can be present but not establish the entire required category. Some reviewed reports combine income items or do not quantify prohibited product/business shares. Other mappings remain uncertain. The SEC API returns standardized disclosed facts; it cannot supply a breakdown that has not been separately established. For example, a retailer's broad food category does not reveal the prohibited-food share, and net interest does not reveal gross interest. No absent disclosure was converted to zero.

The 31 review cases are neither halal nor haram verdicts. Their per-company disclosure candidates, source links and remaining checks are in [recovery_summary.json](../reports/validation/screening_field_recovery_20261020/recovery_summary.json). All 50 decisions are in [results.md](../reports/screening/ftse_yasaar_2025/results.md). All portfolio eligibility flags remain false. This task does not alter the stock-price training data or retrain a prediction model.

## Source preservation and reproduction

Original archives remain unchanged. Supplementary API files and inventories remain in ignored raw/interim folders, not Git. They are available in the separately supplied **Halalify-screening-recovery-evidence-20261020.zip**, SHA256 `be0e7a73cad97216af10762f1055bacc25602f04ed98271d6a0c737c0dd39c14`. It contains only the new 102 files; the original SEC ZIP and earlier extracted candidate set remain separate prerequisites. A Git pull brings code and selected results, not large source datasets.

To reproduce the registered V4 results, install the exact retained source files at the paths in [screening_methodology.md](screening_methodology.md), then run the screening command there. To collect a genuinely new snapshot, use new output folders and review/register their hashes before screening; never overwrite the pinned snapshot:

```bash
python -m src.data.collect_screening_fields --repo . --out data/raw/NEW_API_SNAPSHOT
python -m src.data.recover_screening_notes --repo . --archive data/raw/sec_screening_evidence/sec_sources_20261002.zip --out data/interim/screening/NEW_NOTES_SNAPSHOT
python -m src.data.check_screening_api --api data/raw/NEW_API_SNAPSHOT --notes data/interim/screening/NEW_NOTES_SNAPSHOT --out reports/validation/NEW_CROSSCHECK.json
```

The source-specific table and classification mappings are versioned in `configs/screening_recovery_mappings.json`. They stop on a different issuer, accession, source hash or table content. True value conflicts, unreviewed custom names, business segments, mixed/net interest and incomplete categories remain unresolved. See [the generated recovery report](../reports/validation/screening_field_recovery_20261020/recovery_summary.md) for all 50 companies.

Verification: **56 software tests passed** in the isolated Python3.12 environment, with two upstream deprecation warnings; pip check passed. Arithmetic, cohort, source availability and portfolio-safety checks passed. These are software checks, not 56 passing stocks. No peer/domain approval or complete public-disclosure coverage is claimed.


## Latest follow-up — 20 October 2026

Read [data_completion_20261020.md](data_completion_20261020.md) for the executed source search and price rebuild. V5 screening is 0 complete passes / 20 failures / 30 reviews, with 37 gross-interest candidates. Earlier V4 counts and claims that the training notebook was unchanged apply only to that earlier task. The new 118,643-row price research dataset and repaired notebook are separate from screening. No full Colab model fit, higher accuracy, live screening API, domain approval or portfolio backtest is claimed.
