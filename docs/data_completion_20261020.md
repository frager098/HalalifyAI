# Data repair and source search — 20 October 2026

The prediction dataset and Shariah screening use different information. Daily prices train the return/risk models. Company activities and financial amounts are used for screening. An incomplete screening result does not mean the price dataset has missing income predictors: this experiment has no SEC predictors.

## Training data actually rebuilt

The current teammate table has 124,987 rows, all marked `core_ready=False`, `adjustment_verified=False` and `identity_history_verified=False`. The Colab notebook converted “no large daily move” into a verified return transition and “nonzero volume” into verified share basis. These implications are invalid. It also imported feature/target modules missing from develop and checked out an older branch. The cleaner did retain its uncertainty flags; the notebook bypass was the defect repaired here.

Restored the numerical source checks and the 16-feature/20-session research functions. Re-executed the audit against saved original Alpaca bars, raw-reference pages and action responses, not guessed flags. The audited CSV reproduces SHA256 `3eff4484f22a4e9b5c921541adbadfe3b37022a0d11c52c4742af3fbd7767df1`. It contains 127,501 price rows for 50 companies and SPY. Unsupported action transitions remain excluded from every affected past-feature/future-label window.

The new `data/processed/price_repair_20261020/research_rows.csv` has **118,643 usable rows**, all 16 predictors and three numeric future targets finite. Splits are 58,157 training (2016–2020), 24,150 validation (2021–2022), and 36,336 retrospective test (2023–2025). The full company/session audit has 125,700 rows; 7,057 were excluded for warm-up, gaps/actions, unseen future sessions or partition purges. SPY supplies market features and excess-return targets, not company modeling rows. Classes use training-only thresholds.

These fixed-year splits follow the previously implemented proposed v1.1 research profile, rather than the teammate table's 70/15/15 dates. The old table, its metadata, and the cleaning notebook remain unchanged. The new audited price snapshot equals the previously tested price input; this is an integration repair, not evidence that a new provider or a new score is better. Five companies have adjusted-price differences from the teammate's newer snapshot; the cause and performance impact are not established. Full raw issuer history/action completeness and historical bar arrival times are not certified.

The Colab notebook now reads develop, requires the exact source-checked audited CSV (or its ZIP), rebuilds features/targets, retains excess-return tasks, and rejects the unsupported fallback and synthetic SPY reconstruction. Saved outputs were cleared. All code cells compile and data preparation was executed. The complete Colab environment, LazyPredict/Optuna model fitting and ONNX exports have **not** been run here. Cleaning does not promise high prediction accuracy. The 2023–2025 test period was already inspected; it cannot be advertised as an untouched test.

The notebook's actual data-preparation cells 12 and 14 were executed on the audited input and reproduced the same three partition counts. Copies of the new data were installed and checksum-verified in the user's existing local project under `data/interim/prices/price_repair_20261020/` and `data/processed/price_repair_20261020/`. A separate `Halalify-price-repair-20261020.zip` contains the audited CSV and rebuilt tables for sharing; selected checksums are committed in the data-package manifest. These generated data files stay outside Git.

Reproduction from saved sources:

```text
python -m src.data.price_audit --prices DUAL_BASIS_CSV --raw RAW_REFERENCE_CSV --actions SAVED_ACTION_FOLDER --repo .
python -m src.data.build_price_research --prices AUDITED_CSV_PRINTED_ABOVE --repo . --version NEW_VERSION_NAME
python -m src.data.verify_price_research --prices AUDITED_CSV_PRINTED_ABOVE --dataset data/processed/NEW_VERSION_NAME --out reports/validation/NEW_VERSION_NAME/independent_checks.json
```

These commands preserve old inputs and refuse to overwrite the processed version. Reports are in `reports/validation/price_repair_20261020/` and the new audit report directory. Raw/intermediate/model-ready files stay ignored by Git; code and selected results are committed.

## Additional screening fields actually recovered

| Company | Separate annual interest income | Period ended |
| --- | ---: | --- |
| AMD | USD182 million | 2024-12-28 |
| Cisco | USD1,001 million | 2025-07-26 |
| AbbVie | USD648 million | 2024-12-31 |
| Lowe's | USD159 million | 2025-01-31 |

Original table rows, year headers, USD-million units, issuer/accession and file hashes bind each mapping. AbbVie/Lowe's present earned interest as an offset to expense; the recovered income is positive. These are separate interest candidates, not complete prohibited-income totals.

Union Pacific's original contractual-obligations footnote establishes USD108m finance-lease liability. Current plus noncurrent debt/lease carrying amounts total USD31,807m. Removing the lease liability gives a USD31,699m debt floor against USD68,647m assets: **46.1768%**, above the Yasaar initial debt limit. Future contractual payments including interest are not carrying debt. The runner checks the exact original narrative and source hash before using this mapping.

The fixed 2025-12-31 screening rerun now has **0 complete evidenced research passes, 20 initial-filter failures and 30 reviews**. Gross-interest candidate coverage improved from 33 to 37 companies; other reported-amount coverage is unchanged. All 50 portfolio eligibility flags remain false. The remaining company/product revenue and full income breakdowns are not established; no missing value became zero. `financial_field_ledger.csv` gives all 50 companies' selected amounts, bounds, candidate status and original links. It is screening review data, not an ML feature table or a complete set of approved ratios.

## Other sources actually checked

| Source | What was checked | Outcome for our missing fields |
| --- | --- | --- |
| [Kaggle Figurewell SEC financials](https://www.kaggle.com/datasets/cybermaxtools/figurewell-sec-xbrl-financials) | Downloaded original ZIP/metadata and scanned its numeric facts; 24,036 key-metric filings, all 50 original issuers represented by CIK. | Rolling 2025Q3–2026Q2 filings, not ten years. Key metrics omit complete gross/prohibited income and prohibited-product revenue. Future filings excluded from the historical comparison. Detailed interest candidates are retained for source review; no unverified values joined. |
| [Kaggle US fundamentals](https://www.kaggle.com/datasets/usfundamentals/us-stocks-fundamentals) | Publisher metadata and public listing. | Latest listed update 2019; cannot supply 2025 missing figures. |
| [Kaggle 200+ indicators](https://www.kaggle.com/datasets/cnic92/200-financial-indicators-of-us-stocks-20142018) | Publisher data card. | 2014–2018 annual snapshots; different annual target, missing values and outliers disclosed by publisher. |
| [Kaggle NYSE](https://www.kaggle.com/datasets/dgawlik/nyse) | Publisher data card. | Financial records stop in 2016; unsuitable for the current cutoff. |
| [HalalWallet open screening data](https://www.halalwallet.us/data/halal-stock-screening-data-us) | Downloaded JSON and compared ticker/date/method coverage. | 49 of our tickers, 2026 dates and AAOIFI. Kept as an external research source; not substituted for 2025 Yasaar amounts. Publisher verification flags are not our independent verification. |
| [Musaffa business API](https://musaffa.com/for-business/) | Provider product page. | Offers screening data via business access. No credentials/contract supplied, no contact or purchase made; historical Yasaar-compatible coverage not established. |

Exact public download URLs, dates and SHA256 hashes are retained in the source manifest. Kaggle searches returned other countries, prices-only and single-company data too; titles alone were not accepted as complete data. A third-party estimate, different-period figure or differently defined rule cannot be inserted merely to make the sheet complete. No claim that every public source has been exhausted.

## Verification and remaining limits

All **70 software tests passed**, with two upstream deprecation warnings. Independent NumPy calculations reproduced every retained row's three forward targets (maximum absolute error below 7e-15), class thresholds, chronology and future-action exclusions. All 50 screening arithmetic/decision/date checks passed. These are data/software checks, not 70 passed stocks or a new model-accuracy score.

The full income/business categories still need source-specific evidence or appropriately licensed research with matching definitions/dates. No fully evidenced screening pass is claimed. No model retraining, model improvement, portfolio backtest, religious approval or peer approval was fabricated. Direct develop publication is specifically authorized by the user; no new branch is needed.
