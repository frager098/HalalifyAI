# Screening methodology status

2026-10-02: the user explicitly confirmed that the teammate has **not decided** a Shariah standard or edition. The earlier MSCI reference is a proposed example, not the selected standard. No ratios, thresholds, business exclusions or prohibited-income definitions are approved by this implementation.

`src/data/prepare_screening_handoff.py` produces 50 dated evidence packs from retained financial candidates. Facts cannot be available before their recorded next-session availability date. Alternative tags, debt components and period scopes stay separate. Verified BAC issuer identity is preserved; original source names are retained. XOM predecessor evidence is kept with provenance.

Approved metrics remain null. Every company's status is `needs_review` and `portfolio_eligible=false`. Missing activity evidence, interest-bearing securities, income categories or suitable debt/revenue mapping cannot be replaced with zero. Financial extraction is not a halal verdict.

After a standard and edition are selected, the teammate must record the exact threshold denominators, debt/security/cash definitions, compatible reporting periods and business/income evidence. The reviewer must approve company-specific mappings and the methodology. Historical screens require evidence that was actually available on each screening date; today's company description or ratio must not be copied into past years.

Do not expose these evidence candidates as approved screening results in the backend. Unit fixtures can test calculations after definitions are agreed; they cannot substitute for domain review.
