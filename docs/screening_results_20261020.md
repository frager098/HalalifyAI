# Screening results for all 50 stocks

Executed on 20 October 2026 using SEC information available by **31 December 2025**. These are fixed-version FTSE Yasaar public-rule research results, not present-day verdicts or official Yasaar approval.

| Result | Companies | Meaning |
| --- | ---: | --- |
| Complete evidenced research pass | 0 | No company has every required category established completely. |
| Fails an initial filter | 20 | Available evidence already breaches a rule. |
| Needs review | 30 | More evidence is required; neither a pass nor a failure is established. |

**Zero confirmed passes does not mean all 50 are non-halal.** It means the available dataset cannot establish a full pass. A low debt figure alone is insufficient.

Fourteen debt-filter failures: **AVGO, ORCL, HD, LOW, SBUX, MCD, LLY, TMO, DE, HON, UPS, UNP, MA, NEE**. Cash/interest-bearing-items failures: **AAPL, NVDA**. Four source-specific conventional-finance activity failures: **JPM, BAC, GS, MS**. The latter are research interpretations of the original business descriptions, without an invented prohibited-income percentage.

After the additional field search, every company has an original asset and cash observation. At least one usable debt amount was found for 49, a receivable observation for 47, an annual revenue candidate for 48 and a gross-interest candidate for 37. These are candidate-coverage counts, not full financial-category clearances. Complete prohibited-income evidence remains unestablished for all 50.

The remaining work is source review: reconcile complete borrowing, investments and receivables; identify prohibited business revenue; and establish gross interest plus all prohibited income against a consistent total-revenue denominator. If a disclosure is absent or combined/net, it cannot be filled with zero. Per-company next steps and original filing links are retained in `reports/screening/ftse_yasaar_2025/remaining_review.json`.

Read [all 50 rows](../reports/screening/ftse_yasaar_2025/results.md), the [CSV](../reports/screening/ftse_yasaar_2025/results.csv), or the [full evidence JSON](../reports/screening/ftse_yasaar_2025/results.json). Download/open `results.html` for a simple table with SEC links. Code is under `src/screening/`, thresholds are in `configs/yasaar_research.json`, and the exact scope is in [screening_methodology.md](screening_methodology.md).

This task does not retrain the prediction models, create portfolios or settle domain approval. The initial same-day result was 16 failures and 34 reviews. API/original-note recovery first established three additional failures: Apple, NVIDIA and Lowe's. The later lease-footnote review established Union Pacific's debt failure, bringing the total to 20. Read [the recovery explanation](screening_field_recovery_20261020.md) and [latest source search](data_completion_20261020.md). New API responses are supplemental current snapshots; only matching original filings available by the 2025 cutoff determine this screen.

Latest source search, actual price rebuild and V5 screening findings: [data_completion_20261020.md](data_completion_20261020.md). Earlier V3/V4 execution notes are historical.
