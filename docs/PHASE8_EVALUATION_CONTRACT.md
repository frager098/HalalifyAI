# Phase 8 reserved-period evaluation contract

## Status

Step 8.2 is frozen before Phase 8 features, labels, or scores are created. The
machine-readable authority is `configs/phase8_evaluation_contract_v1.json`.
The accepted clean snapshot remains outcome-blind.

## Chronology

- Training information may end no later than 2025-12-31.
- Because labels require 20 later sessions, the final eligible training
  decision date is 2025-12-02 and its target ends on 2025-12-31.
- The one-time reserved evaluation is 2026-01-02 through 2026-09-30.
- Prices through 2026-10-28 support the final evaluation label.
- The 2025 overlap provides trailing feature history and continuity evidence;
  it is not evaluated.

The previously viewed 2024–2025 period may now enter the training-only role
because Phase 7 selection is frozen. It remains ineligible for any blind-test
claim and cannot be used to reopen selection.

## Frozen procedures

Return uses `momentum_20d` as a no-fit ranking control. Risk uses trailing
`volatility_20d`, classified with pooled training-only risk tertiles:

- Low upper inclusive: `0.18488299831813548`
- Medium upper inclusive: `0.2816141905811629`
- Training rows: `120987`
- Training class counts: `40329 / 40329 / 40329`

The return primary metric is mean same-date Spearman correlation with future
20-session return. Risk primary is macro F1. All secondary and safety metrics,
eligibility rules, source identities, and failure rules are listed in the JSON
contract. Probability metrics are not applicable to the hard-class risk
benchmark and must not be fabricated.

## Interpretation rule

Phase 8 is evaluation, not another model-selection round. Every declared result
must be reported, including unfavorable or undefined metrics. No 2026 result
may trigger a feature, cutoff, metric, model, or date change and still retain
the same test claim. A changed procedure requires a different future period.

This is not portfolio, trading, whole-market, or Shariah-screening evidence.

## Step 8.5 procedure freeze

Phase 7 retained simple benchmarks, so Step 8.5 performs no estimator fitting.
The exact executable procedures are frozen in
`configs/phase8_procedure_freeze_v1.json`:

- return ranks stocks directly with `momentum_20d` and has no fitted parameter;
- risk maps `volatility_20d` with the two already frozen training-only cutoffs;
- no scaler, estimator, calibration object, probability model, or model artifact
  exists; and
- reserved outcome values remain unread until the one-time Step 8.6 evaluation.

Calling this “trained models” would be inaccurate. It is a validated no-fit
procedure freeze ready for one-time evaluation.
