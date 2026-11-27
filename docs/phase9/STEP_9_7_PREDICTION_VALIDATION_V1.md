# Phase 9.7 prediction-output validation

The reviewed inference function is `src/model_training/phase9_prediction.py::predict_phase9`. It calls the Phase 9.6 historical feature reconstruction, verifies both versioned package model hashes and class-code order, then returns return and risk class probabilities for each active ticker. Return ranking uses `P(Higher)-P(Lower)` descending with ticker ascending on exact ties. The response states after-close timing, 20 trading sessions, model versions, and `development_only` evidence. It does not return expected percentage return, Shariah status, or portfolio weights.

The compact no-fit report is `reports/model_evaluation/phase9_prediction_validation_v1/report.json` (SHA-256 `47f77196cc6af37fbe8bdd67b1655adcb4c39bcba781168e03071b962a973a0e`). It records deterministic repeated inference and valid probability totals for 49 stocks on 2016-03-31 and 50 stocks each on 2021-06-25 and 2024-05-30. The saved 2024 AAPL package fixture probabilities are reproduced by the complete feature-to-model path. Five focused tests pass, including missing-peer, stale-date, and missing-package failures.

Run the focused tests from the repository root:

```powershell
.\.venv-phases\Scripts\python.exe -m pytest tests/test_phase9_prediction.py -q -p no:cacheprovider
```

The report performs no model fitting and does not score future outcomes. These dates are historical reproducibility fixtures, not an untouched performance test. Input market bars and a verified point-in-time ticker roster remain required. Source-arrival timestamps and full historical security membership remain unresolved upstream.
