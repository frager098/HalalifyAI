# SEC evidence for your screening teammate

This work adds the missing **source material** for business and income review. It does not label a company halal or non-halal. The user confirmed that the screening standard and edition are still undecided.

A company description explains what the business does. A revenue breakdown shows which products or business divisions earn its sales. Interest income is money earned from lending or interest-paying investments. These are different from share prices, cash balances and debt.

## Executed validation, 2026-10-03

Processed 2,214 original reports with zero extraction exceptions. Retained 538 dated annual business excerpts, including a latest study-issuer excerpt for each of the 50 companies. Each company has revenue source records with business/product dimensions; this does not certify every year or every prohibited product's percentage.

The cleaned file contains 301,669 numeric source records, including repeated representations and reporting periods. Removed 92,672 lexical revenue search false matches. Recovered 5,089 explicitly tagged fixed-zero records. Verified 34,639 retained CompanyFacts records against exact original whole-entity facts; 40 unmatched records remain excluded from usable API candidates. Seventy-one unsupported/blank numeric records remain unknown. Those 111 records are in `reports/validation/screening_evidence/sec_2015_2025_v2/source_review_records.json`; many are non-monetary or balance-related search candidates, not necessarily missing screening income.

Separate gross interest-income candidates were not established for AAPL, MSFT, HD, SBUX, MCD, COST, UPS, V, MA and PEP. This is an extraction/evidence status, not a statement that these companies earned zero interest or that no further disclosure exists. Original notes and combined/unallocated income candidates are retained.

Fresh Python 3.12 environment: 52 tests passed, dependency check passed. Repeated original-source extraction and cleanup reproduced all three intermediate-file hashes and the complete coverage JSON exactly. The Windows installation helper passed isolated install, repeat-install and conflict-preservation checks. No peer/domain approval or develop merge is claimed.

## Collected sources

The saved study-issuer corpus contains 560 annual reports (10-K and amendments) and 1,638 quarterly reports (10-Q and amendments), filed between 2015-01-01 and 2025-12-31. An amendment is a later correction or addition; it is retained separately. Sixteen additional reports preserve related issuers for AVGO and Google's earlier parent-company structure. They are explicitly marked predecessor candidates, requiring historical instrument/issuer mapping review.

Separate original XBRL files were recovered for older reports that did not put their machine-readable numbers inside the report's HTML. Eleven amendments did not supply a separate instance; their original narrative documents are retained for review. A missing structured instance does not mean the amendment has no financial changes.

The [SEC CompanyFacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) aggregates standard-taxonomy, whole-entity facts. It cannot supply every custom company concept or segment breakdown. This extractor therefore reads the original annual/quarterly report and its inline or separate XBRL, retaining context, reporting period, currency and dimensions. A dimension identifies a particular division, product, region or other reporting slice.

AVGO related sources: [2016 merger filing](https://www.sec.gov/Archives/edgar/data/1054374/000119312516446902/d114920d8k.htm), [2018 U.S. redomiciliation](https://investors.broadcom.com/news-releases/news-release-details/broadcom-completes-redomiciliation-united-states-0). Google related source: [2015 Alphabet holding-company reorganization](https://www.sec.gov/Archives/edgar/data/1652044/000119312515336577/d82837d8k12b.htm). These references support retaining the related evidence; they do not approve financial continuity or double-counting parent/subsidiary amounts. XOM uses historical study issuer CIK 34088. BAC numbers require the original filing's issuer context, preserving the earlier identity investigation.

## Files to use

| File | Purpose |
| --- | --- |
| `data/raw/sec_screening_evidence/sec_sources_20261002.zip` | Compressed original source files, retrieval metadata and SHA-256 fingerprints. The Python extractor reads it directly; no manual extraction is needed. |
| `data/interim/screening_evidence/sec_2015_2025_v2/business_evidence.jsonl` | Dated annual business descriptions, source links, literal activity mentions and report text/table excerpts. Each line is one report record. |
| `data/interim/screening_evidence/sec_2015_2025_v2/numeric_candidates.jsonl` | Individual revenue and income facts, exact amounts, periods, currency, reporting slices and source identity. Each line is one source fact. |
| `data/interim/screening_evidence/sec_2015_2025_v2/screening_review_packets.json` | Summary for each of the 50 companies. Approved income amounts remain empty. |
| `reports/validation/screening_evidence/sec_2015_2025_v2/coverage.json` | Actual extraction counts, errors, source verification and output fingerprints. |
| `reports/validation/screening_evidence/sec_2015_2025_v2/review_index.md` | Readable company-by-company review starting point. |

Large source/intermediate files remain outside Git, as the project plan requires. A teammate needs the source archive and intermediate folder as well as the code branch. A clean Git status does not prove those local datasets exist. Copies must match the recorded fingerprints.

## Meaning of the checks

Amounts are exact decimal strings in USD after the report's scale/sign transformation. The displayed number is retained: a report may display `123` in millions, corresponding to `123000000`. Unknown number transformations and missing dates/units stay unknown.

An explicit `ixt:fixed-zero` tag means zero under the [XBRL transformation registry](https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2020-02-12/inlineXBRL-transformationRegistry-REC-2020-02-12.html). This is different from treating an untagged dash, an empty cell or an undisclosed income category as zero. Other unsupported transformations and blank numeric facts remain flagged for review.

An issuer identifier (CIK) tells us which legal company reported the number. Foreign/joint-filer contexts are retained but cannot become usable study-company figures. A CompanyFacts number counts as verified only when concept, issuer, filing, period, unit and value match an original whole-entity filing fact. Segment figures cannot verify whole-company amounts.

The information becomes available from the next exchange session after its filing/acceptance date. Reporting period and availability date are distinct. Later corrections remain later versions. No latest value is silently copied into past screening dates.

Separate gross interest income, net interest after expenses, interest plus dividends, interest plus fees, and other unallocated income remain separate. Noncontrolling/minority interest means ownership, not interest earned on lending. Never sum duplicate inline/API representations, overlapping periods, segment components and whole-company totals. These are review candidates, not approved denominator/numerator values.

Annual report headings differ. The extractor handles formal Item 1 headings and verified issuer-specific business headings. References inside paragraphs cannot end a section. Reorganized excerpts are explicitly not certified complete Item 1 disclosures. Quarterly reports retain numbers and text evidence; their Item 1 financial statements are not mislabelled as a business description.

Literal words such as alcohol, pork, banking or insurance are only search aids. A mention may describe a supplier, employee benefit or risk. It is not an automatic business exclusion.

The search index retains at most 60 activity mentions per business excerpt, 30 income/segment text matches per report and 50 interest-labelled table rows. These shortcuts are not a complete disclosure search. The full saved original report remains the review source.

## Reproduce

Use Python 3.11 or 3.12 and install the pinned requirements. With the saved source archive in the stated folder:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m src.data.extract_screening_reports --archive data/raw/sec_screening_evidence/sec_sources_20261002.zip
python -m src.data.clean_screening_candidates
python -m src.data.summarize_screening_evidence
```

To collect a new snapshot, use a new run folder, the original company-facts inputs, the verified XOM historical snapshot and a real project contact in `--user-agent`. Run `collect_screening_reports` separately for annual and quarterly forms, followed by `collect_legacy_instances`. The saved run configuration is in `configs/sec_screening_evidence.json`. Never silently overwrite immutable source bytes or label a new provider response as the old snapshot.

The cleanup step removes lexical search collisions such as `AvailableForSaleSecurities` and cash proceeds on asset/security sales from revenue candidates. It recalculates coverage from the retained source records. It does not alter the original source files or approve a revenue total.

## What remains before a screening result

Your teammate must select and document the standard/edition, interpret the business and segment sources, approve compatible company-specific amounts and review income completeness. A business division's broad revenue category may not separately disclose prohibited products. An income note may combine interest with another income category. If a required amount is not disclosed, record `needs_review` or `insufficient_data`; do not invent a value or use zero.

Annual/quarterly evidence alone is not a certified daily business-history timeline. Material changes, incorporated documents, amendments, related-issuer continuity and any relevant event filings must be reviewed for the intended screening dates. No historical compliant backtest or backend halal status is authorized by this evidence collection. All current evidence packets remain `needs_review`, with portfolio eligibility false.
