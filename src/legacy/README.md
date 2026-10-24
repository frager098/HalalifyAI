# Legacy research code

This package preserves the modeling and target-generation workflow used before
the Phase 3 dataset, Phase 4 frozen protocol, and Phase 5 classifier pipeline.
It remains available for reproducing earlier benchmark results, but it is not
the current modeling entry point.

- `target_generation/` contains the previous target-generation implementation.
- `model_experiments/` contains the earlier feature comparison, walk-forward, monthly
  ranking, and reused-test evaluation workflow.

Current code remains under `src/feature_engineering/`,
`src/target_engineering/`, and `src/model_training/`.
