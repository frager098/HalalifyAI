# Phase 9.5 risk package

The versioned research package is `reports/model_evaluation/phase9_risk_package_v1/`. It copies the exact 9.2c HistGradientBoosting artifact; no model is refitted. The copied model SHA-256 is `5e05f753e21fbbe3c528f5e6d25707ee9080cb61a91afcbd3826ec7258465fae`, identical to the final-fit source. Package manifest SHA-256 is `61fd008dd378f410d81f9083ef60d9633e63b99577fe447f23afbebe5b3b268d`.

`manifest.json` records `phase9_risk_v1`, seven-feature order, class codes `[0, 1, 2]` as Low/Medium/High, 31 maximum leaf nodes, the 101,087-row development training period, dependencies, and source/contract/9.3 hashes. The risk outcome cutoffs, derived from final training rows only, are `0.18147671306250138` and `0.27948690312156266`. For a realized-volatility outcome, Low is at or below the first cutoff, Medium is above the first and at or below the second, and High is above the second. These cutoffs define historical target labels; the fitted model predicts class probabilities from features. They are not Shariah thresholds.

`fixture_input.json` contains one frozen AAPL feature row from 2024-05-30. A separate Python process reproduced probabilities `[0.4478840178147259, 0.4014692467767355, 0.15064673540853857]`, giving predicted class Low. It also classified exact and next-representable values around both cutoffs as `[Low, Medium, Medium, High]`. The probability tolerance was `1e-12`. This verifies serialization and cutoff semantics, not predictive accuracy.

The builder/verifier is `src/model_training/phase9_risk_package.py`. To verify the existing package without fitting, run from the repository root:

```powershell
.\.venv-phases\Scripts\python.exe -c "from pathlib import Path; from src.model_training.phase9_risk_package import verify_risk_package; print(verify_risk_package(Path('reports/model_evaluation/phase9_risk_package_v1')))"
```

The package is development-only. Historical raw-bar feature reconstruction and complete prediction-output checks remain steps 9.6 and 9.7. No Shariah or portfolio result is included.
