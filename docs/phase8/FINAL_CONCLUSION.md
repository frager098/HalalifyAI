# Phase 8: Final research conclusion

Status: frozen research conclusion based on the single reserved evaluation from 2026-01-02 through 2026-09-30. The 2024–2025 evidence was previously viewed and served only as development evidence. No result from that period is described as a blind test.

## Retained procedures and observed results

Phase 7 selected two deterministic simple benchmarks. Return uses `momentum_20d` to rank the 50-company universe; its score is not a predicted percentage return. Risk maps trailing `volatility_20d` to Low, Medium, and High with training-only cutoffs `0.18488299831813548` and `0.2816141905811629`. No estimator, scaler, probability model, or fitted model binary exists.

The reserved evaluation covered 187 sessions and 9,350 eligible company-date rows, with no exclusions. Mean daily return Spearman was `0.013061481277002776`, versus `0.0005774563696639388` across four Phase 7 development folds. Mean top-10-minus-universe *future 20-session return difference* was `0.01468055223257987`; this overlapping-window research statistic is not a realizable portfolio return. Return ranking association is positive but small and lies within the earlier fold range.

Reserved risk macro F1 was `0.5536780089009589`, versus the Phase 7 development-fold mean `0.5325990982925246`. High-risk recall was `0.7322999581064097`; Low-risk recall was `0.3944672131147541`. Of 4,774 actual High-risk outcomes, 176 were classified Low (`0.03686635944700461`). The risk benchmark is a limited price-risk control, with noticeably weak Low-class recall. Development-versus-reserved differences are descriptive and are not a significance test or a new acceptance threshold.

The frozen procedures are retained as research controls without tuning, recalibration, feature changes, or a new selection round. These results do not establish strong return prediction or uniformly strong risk classification.

## Frozen artifact identities (SHA-256)

| Role | Repository-relative path | SHA-256 |
| --- | --- | --- |
| Phase 7 selection | `configs/phase7_model_freeze_v1.json` | `de41f74592e4ed3ccc0deea7e271325ba725a9f287f6748d5ec7b695e1f35caa` |
| Phase 8 evaluation contract | `configs/phase8_evaluation_contract_v1.json` | `0975fe087ff46b854a85be8dcc57cd7d5d6acd4ec0392e85ecd85fe171f351ee` |
| Procedure freeze | `configs/phase8_procedure_freeze_v1.json` | `633fa647ccb8a5242cb39b942d690d1575979891782ffc444d301e8b68f2a81d` |
| Review contract | `configs/phase8_review_v1.json` | `1d94ef97234d510d04b2d3a29ae600cc5f219e5ee174f623a0a64267532bb1dc` |
| Reserved dataset | `data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1/reserved_features_and_labels.csv` | `389aedcf19eca331c7eed048229deadc5c649c4def8c727c4bf0c8edb3b5a411` |
| Dataset metadata | `data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1/dataset_metadata.json` | `8faf524e2965550ef2c35e4279c4d96adf00790ad593395831ddc38bc2377f27` |
| Dataset validation | `data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1/validation_report.json` | `57b36d59e4a165dbe8f919dd2e1595a431553e54ea1c97cb5ae37bd35d21e4b1` |
| Runner code | `src/model_training/phase8/runner.py` | `03b389af148a8093a280e207b147c3902c150da7c560ad2b5e6e1c681965e3fe` |
| Evaluation code | `src/model_training/phase8/evaluate_once.py` | `33a47cac424a44801353f19e1eba3a171f3f414ad853c067a58c1f15d8c8e5eb` |
| Review code | `src/model_training/phase8/review.py` | `5f00a8ed49cafa3441d953e7f9a34d082681f255bfc768053f2de8cf01388bc6` |
| Runner validation | `reports/model_evaluation/phase8_reserved_evaluation_v1/runner_validation.json` | `3126b0ace6f681520cc26c480aab03c1054a5b3e69ca587808a404e149dab23e` |
| One-time evaluation | `reports/model_evaluation/phase8_reserved_evaluation_v1/one_time_evaluation.json` | `8d967ae09b73053a9742072f713a9f1ff94ed8045f4344b005a3c7c05af81896` |
| Step 8.7 review JSON | `reports/model_evaluation/phase8_reserved_evaluation_v1/step_8_7_review.json` | `96cbb69d1090de28246313c88db8ab1bbc04d5f5e31a24ff5e09b8a1b83d635f` |
| Step 8.7 readable review | `reports/model_evaluation/phase8_reserved_evaluation_v1/step_8_7_review.md` | `13392514314dffea4311b330566f4992d5688d6fb873195a7a9dea39525155ea` |

This manifest identifies its inputs and intentionally does not hash itself. The large dataset and generated evidence are local artifacts; preserve them with these identities rather than assuming Git tracks them.

## Limits and Phase 9 gate

The current 50 companies were selected with hindsight, creating selection and survivorship bias. The provider's all-adjusted historical prices show documented as-of drift in the overlap, and corporate-action magnitudes have not been independently verified. The reserved period is one calendar segment, and successive future 20-session outcomes overlap. SEC fundamentals remain excluded because the point-in-time readiness gate has not passed. No Shariah methodology, portfolio, execution, or transaction-cost experiment is evaluated here. Do not claim trading performance, whole-market validity, or Shariah compliance from these results.

Phase 9 may begin only with an inference contract that reproduces the frozen feature calculations, cutoff semantics, chronology, and procedure identities. Package the two simple benchmark rules and their metadata; do not describe or save nonexistent fitted models or invent class probabilities. Test historical inference against the frozen definitions and reject missing or unavailable inputs. This gate permits engineering work, not deployment or a claim of strong predictive performance. A changed procedure would require a different future evaluation period for a new untouched-test claim.
