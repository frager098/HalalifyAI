# Notebooks

- `model_evaluation_report.ipynb` is the current evaluator-facing notebook.
- `legacy/` contains earlier baseline, Colab, and embedded data-cleaning
  notebooks retained for historical comparison.

Reusable data and model logic belongs in `src/`; notebooks should call those
modules instead of maintaining separate implementations.
