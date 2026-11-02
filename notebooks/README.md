# Notebooks

- `model_evaluation_report.ipynb` is the current evaluator-facing notebook.
- `feature_ablation_report.ipynb` is the student-run Phase 6 notebook. Its
  first sections verify the frozen ablation contract and inventory every
  candidate or excluded dataset column before feature-group comparisons.
- `legacy/` contains earlier baseline, Colab, and embedded data-cleaning
  notebooks retained for historical comparison.

Reusable data and model logic belongs in `src/`; notebooks should call those
modules instead of maintaining separate implementations.
