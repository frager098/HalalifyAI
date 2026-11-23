# Phase 7 candidate-tuning report

## Scope

Phase 7 compared the frozen return and risk candidates on four chronological
development folds. These are development results, not an untouched final test,
trading result, or portfolio result.

## Return decision

- Decision: `retain_simple_benchmark`
- Selection: `{"benchmark": "momentum_20d", "kind": "simple_benchmark"}`
- Reason: No learned option passed every predeclared benchmark, consistency, and safety requirement.

## Risk decision

- Decision: `retain_simple_benchmark`
- Selection: `{"benchmark": "volatility_20d_with_fold_training_cutoffs", "kind": "simple_benchmark"}`
- Reason: No learned option passed every predeclared benchmark, consistency, and safety requirement.

## Frozen evidence

- Dataset SHA-256: `99957129c288d90f63539577f707f0e04d9ad1be3a847e929b9e54e51e2ba9b0`
- Protocol SHA-256: `cc949ed87cda07a22693e4f1844475d2588078895cef6cd79f8dbaf103995060`
- Phase 6 freeze SHA-256: `312ec2857625ab6d87c90bc1eb61f4a36d637c7255f8a1d86b861df3195c29dc`
- Phase 7 experiment contract SHA-256: `d817a11916228a2af9709daf78dbfca0ecc150f5ab3d45155fed84fd2c42d8fa`

## Limitations and Phase 8 gate

- The 50-stock universe has survivorship and selection bias.
- Twenty-session outcomes overlap, so daily rows are not independent trials.
- The 2024–2025 period was previously viewed and is not a fresh test.
- No SEC fundamental feature was approved for these models.
- Phase 8 requires a genuinely later verified period frozen before its outcomes
  are inspected. Any changed model requires a different future evaluation.
