# Screening gap investigation — V6

The full gap is **not yet closed**. The rerun gives **21 evidenced research failures, 29 unresolved companies and 0 complete passes**, using information available by **31 December 2025**. This is not a current-market screen or official Yasaar approval. The user authorized this continuation on existing `develop`, without another branch.

## What was actually fixed

The old adapter could establish a minimum reported amount, but could not use a safe maximum to clear an individual balance-sheet check. V6 adds that missing ability, without estimating missing amounts.

For example, if a company's entire recognized liabilities are below the debt ceiling, its recognized debt carrying amount must also be below it. Similarly, cash, interest-bearing financial assets and receivables fit within total assets after disjoint nonfinancial asset classes are removed. The implementation subtracts only reported property/equipment, inventory and goodwill/intangibles. It never subtracts overlapping alternatives twice. The asset numerator uses the upper precision bound; subtractions and the asset denominator use their lower bounds. Missing declared precision cannot support a maximum proof. Custom concepts, another currency, another period and segment contexts cannot support these proofs.

This clears **52 individual financial tests**: 2 debt tests, 16 cash/items tests and 34 receivables/cash tests. It does **not** mean 52 stocks pass. The proofs concern recognized carrying amounts; they do not bound undisclosed commitments, face values or an alternative methodology. Exact missing component amounts remain missing. Original lower amounts and their source facts are retained alongside maximum proofs. Conflicting minima/maxima withhold clearance.

GE's original annual filing also resolves one stock decision. Its reported 2024 insurance revenue is USD3.581 billion and consolidated total revenue is USD38.702 billion: approximately **9.2528%**, above the 5% business ceiling. The filing describes its retained life/health reinsurance and annuity operations. Mapping those conventional insurance operations to the public prohibited-finance category is an explicit research assessment, not a religious approval. The lower precision-bound share also exceeds 5%. No whole-company prohibited percentage or complete income inventory is invented. [Original GE annual filing](https://www.sec.gov/Archives/edgar/data/40545/000004054525000015/ge-20241231.htm), [FTSE public rules, section 4.3.1](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-yasaar-global-equity-shariah-index-series-ground-rules.pdf).

## What remains

The 29 unresolved companies still lack a complete supported business/income determination; some also lack a financial clearance. A report often describes several products in one revenue bucket without separating prohibited activities. Extracting that bucket correctly does not establish a zero prohibited amount. Changing an API or using a different company's values cannot fill that information.

`reports/screening/ftse_yasaar_2025/data_request.csv` lists exactly these 29 companies, issuer IDs, source links, missing tests and the historical information requested. Already-cleared checks are removed from each company's missing-check list. Failed stocks are not mislabeled as unresolved merely because other categories remain incomplete.

The remaining route to investigate is **specialist historical screening data or a documented qualified review** of the original reports. Access is not yet obtained. The need for a provider, its exact 2025 coverage, a price and a guarantee of decisive answers have not been established. A provider may also legitimately return an unknown or disputed classification. We must not promise that buying an account will clear all 29.

## Provider checks actually performed

Checked official pages on 20 October 2026:

| Route | Verified finding | Decision |
| --- | --- | --- |
| [Yasaar](https://www.yasaar.org/) | Offers screening/advisory work and identifies its FTSE partnership; official contact is info@yasaar.org. | Prepared the specific historical-data/academic quote request below. Coverage, delivery format, licensing and price remain unconfirmed. The authorized form submission on 21 October returned HTTP 404; delivery is unconfirmed. |
| [Zoya API documentation](https://developer.zoya.finance/docs) | Free sandbox data are randomized. The documented methodology enum lists AAOIFI; the report query is for the most recent report and documents no historical cutoff argument. | Sandbox is unusable as company evidence. Published docs do not verify this project's historical Yasaar requirement. Consumer-app FTSE availability is not proof of API coverage. |
| [Zoya API pricing](https://zoya.finance/api) | Published Advanced personal price is USD139/month; Advanced commercial USD1,399/month. The page's 2025 discount has expired. | These are not a quote or a purchase recommendation for this FYP. Method, historical coverage and team/application sharing rights must first be confirmed. |

No account, API credential or purchase was created. The user subsequently authorized provider contact on21October2026; the official form returned HTTP404 and delivery is not confirmed. No provider's latest AAOIFI label was silently substituted for a historical Yasaar screen. The earlier Figurewell/Kaggle and HalalWallet investigations remain documented in [data_completion_20261020.md](data_completion_20261020.md).

## Prepared inquiry — delivery unconfirmed

**Recipient:** info@yasaar.org

**Subject:** University research enquiry: historical FTSE Yasaar screening evidence for 50 US stocks

Hello Yasaar Research team,

We are building Halalify, a university final-year research project. Could you confirm availability and provide an academic/research quotation for historical Shariah screening evidence for our 50 US company candidates, with an information cutoff of 31 December 2025? We currently have 29 unresolved companies; the attached data-request CSV identifies them and the original SEC sources. We can provide the full 50-company universe if needed.

We implement the public FTSE Yasaar initial-entry filters in v4.6, February 2026, as an explicitly retrospective research exercise. Please distinguish (a) contemporaneous 2025 Yasaar classifications and the edition then used from (b) a later reassessment of 2025-available information using v4.6. We are not requesting a current AAOIFI screen, an inference from index holdings, or a continuing-member buffer decision.

For each covered company, please confirm the issuer, financial and business reporting periods, source filings, when the underlying information became available, methodology/version, prohibited business revenue breakdown, gross interest plus other non-compliant income, the total-revenue denominator, financial ratios, analyst assessment basis and any unknown/ambiguous items. Please distinguish reported values from estimates and later interpretations. A yes/no label without this provenance would not close our research gap.

Please quote separately for the unresolved 29 and the full 50, if possible. Confirm historical coverage before any subscription, delivery format (CSV/JSON or reports), an example report, expected turnaround and permission for our student team to share/use the results in its private research repository and FYP demonstration. Please identify any restrictions on publication or backend/API use. This enquiry does not authorize a purchase or subscription.

Thank you.

**Contact was authorized on21October2026 and the user supplied the reply address privately.** The official contact form returned HTTP404, so successful delivery is not claimed. Gmail was discovered as a fallback but is not yet connected. The public repository excludes the private address and form screenshot. Any cost still requires a concrete quote and approval before purchase.

## Reproduce and inspect

Use the same retained source archive, business/numeric candidate files, API responses and note inventories described in [screening_methodology.md](screening_methodology.md). No new large input dataset is needed for V6.

```bash
python -m src.screening.run_yasaar --repo . --archive data/raw/sec_screening_evidence/sec_sources_20261002.zip --evidence data/interim/screening_evidence/sec_2015_2025_v2
python -m src.screening.verify_results --repo .
python -m src.screening.gap_report --repo .
python -m pytest -q
```

All 81 software tests passed in the isolated Python 3.12 environment. The executed report independently verifies cohort, availability, decimal arithmetic, financial maximum proofs, the GE business calculation, rule decisions and eligibility flags. The original source parser verifies issuer/units/context; the runner verifies original file hashes. The result verifier checks saved arithmetic and metadata; it is not an independent religious review.

Before/after counts and test evidence are in `reports/validation/screening_gap_resolution_20261020/`. Raw/intermediate files stay immutable and ignored by Git. This continuation does not retrain the prediction model or claim better accuracy. All portfolio eligibility flags remain false.

## Completion check and contact attempt — 21 October 2026

All81tests also passed from a fresh exported repository copy. The full source-bound screen reproduced all50decisions, lower ratios, upper proofs and business evidence using the retained input snapshots; input hashes matched. See fresh_checkout_tests.xml and reproduction_checks.json in the V6 validation directory. This is software reproduction, not independent domain or peer approval.

The user authorized the enquiry and provided a private reply email. The official form was submitted but displayed **Error:404 https://www.yasaar.org/forms/contact.php** instead of a success confirmation. Do not state that Yasaar received it or that a reply is pending. Gmail access is the proposed fallback and is not yet confirmed. The screenshot and reply address are retained only in private workspace outputs, not GitHub. No data, price quote or paid access has been obtained. The outstanding-data gap remains29companies.
