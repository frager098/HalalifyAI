# Notebooks

- `model_evaluation_report.ipynb` is the current evaluator-facing notebook.
- `feature_ablation_report.ipynb` is the student-run Phase 6 notebook. Its
  first sections verify the frozen ablation contract and inventory every
  candidate or excluded dataset column before feature-group comparisons.
- `phase6_recovery_validation.ipynb` is the student-run recovery notebook for
  Phase 6.3. It validates the verified Phase 6.2 recovery inputs and writes a
  no-model-fitting comparison plan. It does not create performance results.
- `phase6_momentum_ablation.ipynb` is the student-run Phase 6.4 notebook. It
  fits the predeclared HistGradientBoosting comparison for the full allowed
  market feature set versus the same set without momentum, separately for
  return and risk. It writes new local evidence under
  `reports/model_evaluation/phase6_recovery_v1/momentum_ablation/` and refuses
  to overwrite an existing result.
- `legacy/` contains earlier baseline, Colab, and embedded data-cleaning
  notebooks retained for historical comparison.

Reusable data and model logic belongs in `src/`; notebooks should call those
modules instead of maintaining separate implementations.
