# Provisional model card

2026-10-08: research fits reproduced using the earlier retained audited snapshot after input validation repair. Full Colab/API/ONNX execution and newer-input matched comparison remain unverified. No production-readiness or improved-test-performance claim is supported. See training_data_repair.md.

Purpose: academic classification of next-20-session company return and annualized realized volatility. The two classifiers are separate from Shariah screening. No percentage-return prediction, investment recommendation or compliance certification is supplied.

Population: the collected 50-company cohort, 2016–2025, with separate SPY market inputs. Today's selected company cohort has selection/survivorship bias. Historical ticker/issuer relationships and provider revisions are not universally certified.

Inputs: the dictionary's ordered 16 price/volume/market features, using complete windows. Missing history and unsupported-action windows are excluded. Targets use 20 future exchange sessions and training-only pooled tercile boundaries, stored with the artifact. Class order is low, medium, high.

Training: 58,157 rows in 2016–2020. Selection: 24,150 validation rows in 2021–2022, macro-F1, with the documented 0.01 simpler-family tie rule. Eleven configurations per target were evaluated with seed 42. Selected models remain fitted on initial training rows only. The detailed comparisons and baseline results are in `reports/experiments/core_v1_readiness/`.

Limitations: probabilities are uncalibrated; the final test has not been scored; no final train+validation refit has been performed. There is no production acceptance threshold or live monitoring evidence. Classes are relative to training thresholds, not guarantees of profit or safety. The proposed experiment still needs project/domain agreement.

Artifacts are local under `artifacts/core_v1_readiness/` and ignored by Git. Reports retain their SHA-256 checksums, feature order, parameters, seed and thresholds. Only load trusted joblib files. A teammate must reproduce the result before milestone sign-off.
