# Research reports

Generated research artifacts are organized by task and ignored by Git.

- `literature_review/v1/` contains the saved literature-review evidence.
- `data_validation/v1/consolidated_review/` contains the completed consolidated
  data review. Its `supporting_investigations/` siblings preserve the market
  price audit, market price reconciliation, and point-in-time fundamentals
  investigations used during that review.
- `model_evaluation/baseline_comparison/v1/refactored_evidence/` contains the
  current paths for the frozen baseline comparison. The corresponding
  `pre_refactor_evidence/` directory preserves the experiment before the
  source-module rename, while `pre_path_reorganization_evidence/` preserves
  the evidence immediately before report paths were reorganized. These are
  provenance snapshots of the same v1 experiment, not separate model versions.
- `model_evaluation/feature_ablation/v1/` contains generated Phase 6 contract
  and feature-ablation evidence. The step 6.1 contract and step 6.2 JSON/CSV
  feature inventory must be reviewed before any feature group is evaluated.
- `legacy_model_experiments/` preserves the earlier feature comparison, monthly
  ranking, walk-forward evaluation, and reused-test check. The reused-test
  protocol and results are two parts of one evaluation workflow.

Create `v2` only when an experiment or validation contract materially changes,
such as its inputs, feature set, frozen protocol, model configuration, or
evaluation period. A rerun or source refactor alone is not a new version.

Do not interpret generated results as guaranteed performance, and do not remove
artifacts cited by the project documentation.
