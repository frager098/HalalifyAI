# Screening methodology status

2026-10-02: the user explicitly confirmed that the teammate has **not decided** a Shariah standard or edition. The earlier MSCI reference is a proposed example, not the selected standard. No ratios, thresholds, business exclusions or prohibited-income definitions are approved by this implementation.

`src/data/prepare_screening_handoff.py` produces 50 dated evidence packs from retained financial candidates. Facts cannot be available before their recorded next-session availability date. Alternative tags, debt components and period scopes stay separate. Verified BAC issuer identity is preserved; original source names are retained. XOM predecessor evidence is kept with provenance.

Approved metrics remain null. Every company's status is `needs_review` and `portfolio_eligible=false`. Missing activity evidence, interest-bearing securities, income categories or suitable debt/revenue mapping cannot be replaced with zero. Financial extraction is not a halal verdict.

After a standard and edition are selected, the teammate must record the exact threshold denominators, debt/security/cash definitions, compatible reporting periods and business/income evidence. The reviewer must approve company-specific mappings and the methodology. Historical screens require evidence that was actually available on each screening date; today's company description or ratio must not be copied into past years.

Do not expose these evidence candidates as approved screening results in the backend. Unit fixtures can test calculations after definitions are agreed; they cannot substitute for domain review.

## Original business and income disclosures

The [SEC evidence guide](sec_screening_evidence.md) documents the added annual/quarterly source corpus and version `sec_2015_2025_v2`. Business excerpts come from original annual reports. Original inline/separate XBRL preserves standard and custom revenue/income concepts, issuer contexts and segment dimensions. CompanyFacts amounts require exact original-filing verification before counting as usable source candidates. This is additional evidence, not an approval of the old financial handoff's debt/revenue definitions.

Gross interest income remains separate from net interest, combined interest/dividend/fee/other income, cash receipts and unallocated investment income. Neither combined figures nor broad segment categories establish a complete prohibited-income numerator. Missing disclosure stays unknown. Quarterly narrative changes, event filings, incorporated documents and predecessor continuity require review before certifying historical business eligibility. Every evidence packet still has empty approved income amounts, `needs_review`, and `portfolio_eligible=false`.
