# HalalifyAI: current goal and Phase 9 decision

This brief is for the project team or supervisor. It states the current evidence, the product goal, and the decision needed before implementing the existing Phase 9 plan. Detailed requirements remain in `AGENTS.md` and `docs/Approved phases specifications.md`; completed work is tracked in `docs/Phases.md`. The FYP is the development context and deadline, not the intended limit of the software.

## What we are trying to deliver

HalalifyAI is intended to become usable software that helps people compare and select U.S. stocks based on predicted return potential, future price risk, and separately verified Shariah eligibility. A user should be able to see a ranked set of eligible stocks, understandable risk information, and the reasons and limitations behind those outputs. The first implementation works with a fixed 50-stock universe and a 20-trading-session horizon; those are initial scope limits, not a claim that the final product solves the problem for the whole market. The system does not execute trades.

The approved return task defines Lower, Middle, and Higher classes relative to other eligible stocks on the same date and asks a classifier for their probabilities; its primary evaluation is mean same-date Spearman correlation. The risk task defines Low, Medium, and High from training-only future-volatility cutoffs; its primary evaluation is macro F1, with special attention to actual High-risk cases predicted Low. User-facing predictions must use information available at the prediction time, and a portfolio recommendation must pass the separately approved Shariah screen.

Our desired deliverable is a **working stock-selection product with trained return and risk prediction models**, documented model versions, clear inputs and outputs, and honest later-period evaluation. Research evidence is how we establish what the software can reliably tell users; it is not the product itself. A ranking score must not be presented as an expected percentage return. A risk class must not be presented as Shariah compliance.

## What has been completed

Phases 1–8 established the targets, market-data checks, market features, chronological evaluation, bounded candidate comparisons, and a one-time reserved evaluation for 2026-01-02 through 2026-09-30. Phase 7 trained and compared Logistic Regression and HistGradientBoosting candidates, but none met all of the previously declared advancement rules. The retained return procedure is a fixed `momentum_20d` ranking rule. The retained risk procedure is fixed `volatility_20d` with two training-derived class cutoffs. These are reproducible research benchmarks, not fitted model artifacts.

The reserved Phase 8 evaluation reported mean daily Spearman `0.013061481277002776` for return ranking and macro F1 `0.5536780089009589` for risk. High-risk recall was `0.7322999581064097`; Low-risk recall was `0.3944672131147541`. These results support limited research controls, not a claim of reliably strong return or risk prediction. See `docs/phase8/FINAL_CONCLUSION.md` for the exact artifact hashes and limitations.

## Why the current Phase 9 plan needs a decision

`docs/Phases.md` currently opens Phase 9 with “Save models and verify inference.” There is no selected fitted return or risk model to save, and the fixed rules do not emit return-class probabilities. Packaging those rules can make benchmark inference reproducible, but it does not fulfill the intended trained-model output. This is a **deliverable and roadmap mismatch**, not proof that the source data is incorrectly cleaned or that machine learning cannot work.

The 2026 reserved outcomes are now known. They remain the one-time evaluation of the existing fixed procedures. Any changed model can use those dates only as openly labeled development evidence; a new untouched-test claim requires another future period with complete labels, reserved before its outcomes are inspected. Do not silently replace the Phase 8 result or claim that an improved development score is independent proof of reliability.

## Recommended next decision and bounded path

Revise the roadmap **before** treating Phase 9 as model packaging. Under the one-week FYP constraint, keep the validated market dataset and frozen benchmarks. Select one return model that directly learns same-date ranking and one risk model that forecasts future volatility or its classes. Fix their inputs, training dates, output meanings, comparison metrics, and stop rules before experimentation. Train and save working artifacts even if the models do not beat the benchmarks; report their measured results honestly. Integrate only outputs supported by their evaluation into the user workflow, with explicit coverage and reliability limits.

Potential focused candidates from the supplied research review are a grouped learning-to-rank model such as LambdaMART for returns and a daily-data HAR-style volatility forecast for risk. These are **candidate approaches, not approved selections or demonstrated improvements**. A ranker normally produces an ordering score, not the three required return-class probabilities. A volatility forecast can be mapped to the frozen risk bands, but probability outputs would need a separately validated method. The team must decide whether those output changes are acceptable or whether to prioritize existing probability-producing classifiers. Pretrained financial/time-series models are optional experiments; their availability does not establish compatibility, historical data integrity, or performance on this task.

Do not restart market-data cleaning, add sentiment, or change the dataset solely because the learned candidates were not selected. Investigate a specific defect or secure a time-stamped historical news source before making either change. SEC fundamentals remain excluded until their point-in-time readiness gate passes. The Shariah methodology and portfolio assumptions still require explicit approval before user-facing compliance or portfolio claims.

## Decision to record

**The product goal is a usable stock-selection system with trained return and risk models.** The remaining decision is which model outputs and measured quality level are required for the first user-facing release, and whether the approved probability outputs are mandatory for that release. Record the decision and revise `docs/Phases.md` accordingly. Do not promise predictive reliability that has not been demonstrated on later data.
