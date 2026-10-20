# Screening results for all 50 stocks

Executed on 20 October 2026 using SEC information available by **31 December 2025**. These are fixed-version FTSE Yasaar public-rule research results, not present-day verdicts or official Yasaar approval.

| Result | Companies | Meaning |
| --- | ---: | --- |
| Complete evidenced research pass | 0 | No company has every required category established completely. |
| Fails an initial filter | 16 | Available evidence already breaches a rule. |
| Needs review | 34 | More evidence is required; neither a pass nor a failure is established. |

**Zero confirmed passes does not mean all 50 are non-halal.** It means the available dataset cannot establish a full pass. A low debt figure alone is insufficient.

Twelve debt-filter failures: **AVGO, ORCL, HD, SBUX, MCD, LLY, TMO, DE, HON, UPS, MA, NEE**. Four source-specific conventional-finance activity failures: **JPM, BAC, GS, MS**. The latter are research interpretations of the original business descriptions, without an invented prohibited-income percentage.

Every company has an original asset and cash observation. At least one debt amount was found for 48, a receivable observation for 43, an annual revenue candidate for 48 and a gross-interest candidate for 25. These are candidate-coverage counts, not full financial-category clearances. Complete prohibited-income evidence remains unestablished for all 50.

The remaining work is source review: reconcile complete borrowing, investments and receivables; identify prohibited business revenue; and establish gross interest plus all prohibited income against a consistent total-revenue denominator. If a disclosure is absent or combined/net, it cannot be filled with zero. Per-company next steps and original filing links are retained in `reports/screening/ftse_yasaar_2025/remaining_review.json`.

Read [all 50 rows](../reports/screening/ftse_yasaar_2025/results.md), the [CSV](../reports/screening/ftse_yasaar_2025/results.csv), or the [full evidence JSON](../reports/screening/ftse_yasaar_2025/results.json). Download/open `results.html` for a simple table with SEC links. Code is under `src/screening/`, thresholds are in `configs/yasaar_research.json`, and the exact scope is in [screening_methodology.md](screening_methodology.md).

This task does not retrain the prediction models, create portfolios, settle domain approval or supply new current filings. Earlier counts of 12 failures/38 reviews were superseded by the recovered-source 16/34 result; today's independent run of the retained archive reproduces that 16/34 result.
