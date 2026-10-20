# Screening implementation evaluation

Evaluation scope is screening correctness and retained-source execution, not prediction accuracy. Public threshold boundaries, inclusive/exclusive comparisons, invalid and missing values, overlapping debt totals, issuer/context restrictions, custom mappings, amendment/next-session availability, unknown business mentions and complete-versus-partial decisions are tested.

The executed run has 50 unique company records, exactly the configured cohort, no SPY, no future-available selected source, no eligible portfolio and 0 complete passes / 16 initial-filter failures / 34 reviews. Selected original-report hashes and all three registered source-file hashes are verified. The exact numerical results and provenance are in reports/screening/ftse_yasaar_2025/; execution/reproduction checks are in reports/validation/screening_20261020/.

These counts are not labeled-data accuracy estimates: no independently adjudicated gold-standard set or peer/domain review has been obtained. Unknown cases are not mislabeled as non-halal. No new ML accuracy, calibration or return/backtest score is claimed. Verification details and environment versions are recorded after actual checks, not assumed from the existence of scripts.

Executed verification: a new Python 3.12 environment installed both requirements files successfully; all 46 repository tests passed with two upstream deprecation warnings; pip check found no broken dependencies. The complete retained-source screening rerun reproduced all 50 prior decisions and balance ratios. See reports/validation/screening_20261020/verification.json, tests.xml and result_checks.json. No peer/domain approval is claimed.
