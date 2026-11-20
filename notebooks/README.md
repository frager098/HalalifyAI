# Notebooks

- `model_evaluation_report.ipynb` is the current evaluator-facing notebook.
- `feature_ablation_report.ipynb` is the student-run Phase 6 notebook. Its
  first sections verify the frozen ablation contract and inventory every
  candidate or excluded dataset column before feature-group comparisons.
- `phase6_recovery_validation.ipynb` is the student-run recovery notebook for
  Phase 6.3. It validates the verified Phase 6.2 recovery inputs and writes a
  no-model-fitting comparison plan. It does not create performance results.
- `legacy/` contains earlier baseline, Colab, and embedded data-cleaning
  notebooks retained for historical comparison.

Reusable data and model logic belongs in `src/`; notebooks should call those
modules instead of maintaining separate implementations.
