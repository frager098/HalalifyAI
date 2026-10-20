# Experiment log

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
