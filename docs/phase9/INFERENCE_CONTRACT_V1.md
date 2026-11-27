# Phase 9.2 inference contract v1

The machine-readable specification is [`configs/phase9_inference_contract_v1.json`](../../configs/phase9_inference_contract_v1.json). It fixes the two AI candidate types, feature order, input rules, output meanings, and fitting safeguards. It does not authorize packaging until trained artifacts and their evidence exist.

For an after-close prediction on session `t`, supply daily adjusted close, volume, and same-date SPY return for the complete reference panel through `t`. At least 61 consecutive shared sessions are needed to calculate 60-session return and volatility features. The decision-date peer group must contain 45–50 active stocks from the dataset metadata's reference universe. Duplicate dates, unknown tickers, missing or nonfinite inputs, gaps, and unavailable bars are errors. Historical prediction must use a provider snapshot available at `t`; a current fully adjusted price series cannot by itself prove historical as-of availability.

The return Logistic Regression takes the contract's 17 features in order and returns probabilities for Lower/Middle/Higher. `P(Higher) - P(Lower)` orders same-date stocks, breaking ties by ticker. It is not a predicted percentage gain. The risk HistGradientBoosting takes seven features and returns probabilities for Low/Medium/High future 20-session volatility. These probabilities are uncalibrated; neither prediction implies Shariah compliance.

Examples of contract outcomes:

| Input | Expected outcome |
| --- | --- |
| Complete 61-session, 50-stock panel ending after the close of `t`, with verified matching artifacts | Return and risk classes and three probabilities each; rank score, horizon, date, version, and `development_only` status |
| 60 sessions for every stock | Reject: insufficient 60-return history |
| Duplicate `(ticker, session_date)` | Reject: duplicate panel key |
| 44 active peers on `t` | Reject: fewer than 45 active peers |
| Missing SPY value on `t` or unknown ticker | Reject: missing benchmark or unsupported ticker |
| Valid panel but absent fitted artifact | Reject: model package unavailable; never fall back to benchmark rules |

Final training dates and inner validation dates must be fixed before fitting; the selected hyperparameters, scaler, and risk cutoffs must come only from eligible training data. A manifest must record row/date/class distributions, latest training target end, feature and class orders, dependency versions, and all artifact hashes. The discrepancy in the Phase 6 feature-freeze hash recorded by Step 9.3 must be resolved before packaging. No final fitted model or untouched evaluation of these candidates exists yet. The already viewed 2026 result belongs to the benchmark procedures.

## Proposed model improvements

The team has requested a broader Logistic Regression study: standardization, `C`, class weighting, redundant-feature removal, same-date cross-sectional normalization, and probability calibration. For HistGradientBoosting, the study should cover learning rate, iterations, leaf nodes, minimum samples per leaf, L2 regularization, feature quality, and chronologically controlled early stopping. These are proposed experiments, not settings validated by Phase 7. In particular, Phase 7 used a narrow `C`/leaf-node search and disabled tree early stopping.

Freeze a small candidate grid, feature variants, dates, and acceptance criteria before running the student-facing experiment notebook. Every preprocessing step must fit on earlier training rows. Calibration requires a later, purged chronological calibration block distinct from the rows used to fit the classifier, followed by another block for honest probability scoring. Early stopping must use an explicitly dated, purged validation block; automatic random validation is not acceptable. Report return rank quality and probability metrics alongside risk macro F1, High-risk recall, and High-to-Low errors. Any resulting model is a new candidate version and needs its own evaluation evidence before replacing this contract's Phase 7 candidate specification.
