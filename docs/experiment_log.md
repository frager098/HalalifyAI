# Experiment log

## 2026-10-20 — FTSE Yasaar retained-data screen

Task explicitly authorized on existing develop, starting from remote 2168193957e0778e048319f950ed44aa6b6a760e. No new feature branch. Plan section 7.3 and SRS FR-4.1 through FR-4.4/FR-5.1 informed the independent financial/activity rules and conservative portfolio eligibility.

Reused the source-preserving extraction and field-recovery logic from the earlier unpublished screening prototype, integrated only needed screening dependencies into current develop, and added full-completeness decision handling, independent rule functions, strict limits, cohort checks, source binding, freshness controls, original-report provenance and readable reports. Raw inputs and teammate model data/notebooks remain untouched. Fixed the existing cleaning calendar's pandas 3 timestamp-resolution compatibility discovered by its existing regression test.

Official v4.6 public rules were rechecked online. Selected 50 latest eligible financial and annual sources available by 2025-12-31. Actual rerun: 0 complete evidenced passes, 16 initial-filter failures, 34 requiring review. These reproduce the recovered-source 16/34 result and do not claim additional recovered prohibited-income completeness. See results JSON and validation reports for runtime verification.

No current 2026 data collection, model retraining, domain approval, official index determination or historical eligibility/backtest was performed. More source review is required before any full pass or approved portfolio.

Verification completed: fresh Python 3.12 dependency installation, 46 passing tests, pip check passed, all 50 decisions/ratios reproduced against the earlier recovered-source run. No unsafe portfolio flag or future-available selected source. Provenance checks retain all original file hashes. Publication is a separate recorded action; no review is invented.
