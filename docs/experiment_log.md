# Experiment log

## 2026-10-24 — data code consolidation

User approved consolidation and selected develop's 17-file src/data version.
Focused branch: feature/data-code-simplification from develop c59ff2c. Plan
sections 4.2, 6.1, 7.2 and 10 and SRS NFR-2.2/NFR-5.1/NFR-5.2 guide the modular,
source-preserving change. No model-selection, screening-threshold, stock-universe
or data-provider decision changed; the separate teammate branch was not merged.

Combined price schema/action/input gates, grouped SEC commands, combined note
recovery with report parsing, and retained two source investigations under
src/data/research. There are 10 main Python files and two research tools. The
offline pipeline runs clean -> validate -> build -> independent verification
against an exact configured audited input; historical raw audit evidence is
reused and unknown flags are never promoted. Existing caller, test, notebook
imports and current reproduction commands are updated.

Baseline: 81 tests. Refactor: 91 tests in the existing Python 3.12 environment.
Actual 118643-row research and 125700-row full-audit CSVs are byte-identical to
an independent run of the original builder. No new model accuracy was measured.
See docs/data_workflow.md and reports/validation/data_refactor_20261024 for
equivalence and reproduction evidence. Peer approval and merge are not implied.

All 91 tests also passed from a fresh exported source tree with the original
project's Python 3.13.7 environment. Full retained-source screening reproduced
all 50 complete company records exactly (21 fail, 29 review, zero complete
passes). No missing screening evidence was filled or new accuracy claimed.

## 2026-10-20 — FTSE Yasaar retained-data screen

Task explicitly authorized on existing develop, starting from remote 2168193957e0778e048319f950ed44aa6b6a760e. No new feature branch. Plan section 7.3 and SRS FR-4.1 through FR-4.4/FR-5.1 informed the independent financial/activity rules and conservative portfolio eligibility.

Reused the source-preserving extraction and field-recovery logic from the earlier unpublished screening prototype, integrated only needed screening dependencies into current develop, and added full-completeness decision handling, independent rule functions, strict limits, cohort checks, source binding, freshness controls, original-report provenance and readable reports. Raw inputs and teammate model data/notebooks remain untouched. Fixed the existing cleaning calendar's pandas 3 timestamp-resolution compatibility discovered by its existing regression test.

Official v4.6 public rules were rechecked online. Selected 50 latest eligible financial and annual sources available by 2025-12-31. Actual rerun: 0 complete evidenced passes, 16 initial-filter failures, 34 requiring review. These reproduce the recovered-source 16/34 result and do not claim additional recovered prohibited-income completeness. See results JSON and validation reports for runtime verification.

No current 2026 data collection, model retraining, domain approval, official index determination or historical eligibility/backtest was performed. More source review is required before any full pass or approved portfolio.

Verification completed: fresh Python 3.12 dependency installation, 46 passing tests, pip check passed, all 50 decisions/ratios reproduced against the earlier recovered-source run. No unsafe portfolio flag or future-available selected source. Provenance checks retain all original file hashes. Publication is a separate recorded action; no review is invented.

## 2026-10-20 — follow-up field/API recovery (V4)

User requested recovering whatever further public fields can be found and pushing to existing develop without another branch. Starting point a1d9d1de3498f818ec763e95eb5f07624be552c0. All50 live SEC CompanyFacts downloads succeeded. Inventoried original latest financial and annual notes; 12,482 exact source fact representations matched historical API observations, with later observations excluded. Source dates and original hashes retained.

Added declared-rounding reconciliation, safe debt-instrument scopes, securities/cash overlap handling, source-specific original interest table mappings and explicit mixed/net income categories. Additional failures AAPL/NVDA cash-items and LOW debt change the result to 0/19/31. This is a genuine recovery change, not a claim of full required-field completeness or a current2026 verdict. No original price/historical source dataset changed.

All56 software tests passed and pip check passed in the isolated Python3.12 environment. New reports and source hashes are in reports/validation/screening_field_recovery_20261020. All portfolio flags false; missing prohibited-income/product breakdowns remain unknown. No invented peer/domain approval.


## 2026-10-20 V5 data completion and notebook repair

Recovered four source-bound annual interest rows and UNP lease exclusion; rerun 0/20/30. Downloaded/scanned the Kaggle Figurewell SEC archive, public Kaggle catalogs and HalalWallet JSON; historical/method/category gaps prevented automatic replacements. Restored numerical price checks and 16-feature/20-session functions, removed unverified notebook fallbacks and old-branch routing. Audited price hash reproduced; research rows118643 independently verified. No fresh accuracy claim or unseen test. See data_completion_20261020.md. No new branch; direct develop push authorized.

## 2026-10-20 V6 screening gap investigation

Continued on existing develop from2077c67 at the user's request, without a new branch. Added worst-case declared-precision accounting maximum proofs for recognized carrying amounts, retained existing lower amounts and rejected overlapping/foreign/dimensional/stale-period evidence. Cleared52 individual financial tests, not52stocks. Reviewed GE original annual life/health insurance disclosures; USD3581m/USD38702m reported revenue exceeds the5%business ceiling. Exactissuer/accession/filehash/annualdates/amounts/markers bind that research classification. Rerun0passes/21failures/29review; all eligibilityfalse.

All81softwaretests pass. Recorded per-company missing-data request and official provider research. Zoya free randomized sandbox rejected; its documented API does not verify historical Yasaar coverage despite paid pricing/app methodology marketing. Exact academic Yasaar enquiry drafted. User later authorized contact on21October; officialformreturned404, deliveryunconfirmed. No quote/account/credential/purchase. Complete income and domain review not invented. No new training or claimed performance improvement. Read screening_gap_resolution_20261020.md and reports/validation/screening_gap_resolution_20261020.

## 2026-10-24 V7 free source repair

Approved free SEC/issuer-source repair with unchanged Yasaar rules and 2025 cutoff. Corrected WMT annual revenue candidate from674538m sales to680985m total; recovered CVX296m interest component, CAT482m combined investment/interest and4509m partial short borrowing. All50 now have borrowing observations and38 have gross-interest candidates/components. These are not complete screened totals.

User explicitly approved CAT finance/insurance interpretation after reviewing original3446m/64809m consolidated external revenue share5.317%. New research result0passes/22failures/28review,0portfolioeligible. Source-bound complete-review integration now supports income/business passes and failures with original issuer,period,hash,amount,coverage,disjointness,precision and historical availability checks. Complete real-company registry remains empty: business/income gaps not declared solved. Price data/models unchanged. Read screening_source_repair_20261024.md and versioned reports/screening/ftse_yasaar_2025_v7. No paid access, provider contact, GitHub publication, merge or invented peer/domain approval in this task.
