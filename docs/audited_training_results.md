# Audited training review, 2026-10-08

The user confirms the teammate used the previously supplied project data. No new upload is required for this retained-data review. The exact newer Colab input hash recorded in its manifest remains unavailable; this is a rerun of the retained, rebuilt project dataset, not a matched before/after causal experiment on that newer snapshot.

The confirmed audit bypass and output-routing defects have been repaired. Original downloaded prices were preserved. The audit reproduces 127,501 price rows exactly; feature/target generation yields 118,643 usable observations. Five unsupported company spin-off transitions stay excluded from affected windows. Missing history and immature future answers are never invented. No wholesale re-cleaning, clipping of market moves, or new price download was performed merely to improve scores.

Two frozen validation-selected classifiers were actually refitted on the 58,157 initial training rows. Validation scores reproduce. The same fixed models were then evaluated on the 36,336 eligible 2023-2025 observations. No test-driven model selection, tuning, threshold changes or final train-plus-validation refit was performed. This period had already been examined in earlier team work, so these are retrospective results, not a new independent holdout.

| Prediction | Model accuracy | Previous-20-session accuracy | Model macro-F1 | Previous-20-session macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| Return class | 36.47% | 34.07% | 0.3603 | 0.3369 |
| Volatility class | 54.83% | 52.72% | 0.5520 | 0.5230 |

Accuracy is the percentage of correct predictions. Macro-F1 gives equal weight to how well each of the three classes is identified. Always predicting the most common training return class achieves 38.45% test accuracy but only 0.1852 macro-F1. The return model therefore remains weak: it improves balanced class identification over simple comparisons but does not beat that constant prediction on accuracy. Volatility performance also weakens over time: model macro-F1 is 0.6097 in 2023, 0.5257 in 2024 and 0.4936 in 2025. Neither result establishes reliable investment performance or calibrated probabilities.

A shared every-20-session anchor schedule reduces overlapping future windows; macro-F1 is 0.3608 for returns and 0.5528 for volatility. These are descriptive sensitivity checks, not confidence intervals or independent stock samples. Machine-readable results include per-class confusion matrices, yearly results, log loss and both baseline comparisons.

Reproduce from the project root:

```bash
python -m src.evaluation.audited_training_review --dataset data/processed/core_v1_training_repair_20261008/research_rows.csv
```

The command binds the dataset hash to the frozen validation selection and refuses duplicate company/dates, invalid features/labels and future targets crossing split boundaries. It writes metrics to `reports/experiments/audited_training_review_20261008/` and models to ignored `artifacts/audited_training_review_20261008/`. Prediction CSVs remain local. No new regression evaluation, full Colab/ONNX run, probability calibration, backtest or Shariah verdict was completed in this run.

Next model improvements need a separately documented experiment using chronological validation within development dates, with the existing comparisons retained. Do not keep optimizing against the observed 2023-2025 scores or advertise a guaranteed accuracy. Additional source or feature changes require evidence and data-dictionary updates; artificial data changes are not a substitute for predictive information.
