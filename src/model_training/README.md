# Model training code layout

This package is grouped by research task:

- `chronological_evaluation_protocol.py` and `baseline_models.py` define the
  frozen Phase 4 evaluation setup and Phase 5 baselines.
- The four return/risk classifier modules contain the Phase 5 model runs.
- `evaluate_return_models.py`, `evaluate_risk_models.py`, and
  `build_model_evaluation_report.py` review and present Phase 5 results.
- `feature_ablation/` contains the Phase 6 input contract and candidate-feature
  inventory and controlled ablation runner used by
  `notebooks/feature_ablation_report.ipynb`.

The Phase 4/5 modules remain at this package level because their source paths
and hashes are recorded in frozen experiment evidence. New Phase 6 code belongs
in `feature_ablation/` so later ablation work stays together without changing
that provenance.
