# Phase 9.4 return package

The versioned research package is `reports/model_evaluation/phase9_return_package_v1/`. It copies the exact 9.2c Logistic Regression pipeline and fitted StandardScaler; no model is refitted. The copied model SHA-256 is `e7c0e21f644363f069ffd9d52a2bf0c299fed7cd043e80ba844779ae700d401c`, identical to the final-fit source. Package manifest SHA-256 is `d5025df0007f6e81fd916b3ca9a058bd1c0f5b4c08251c0cf1857a610ac47e86`.

`manifest.json` records model version `phase9_return_v1`, 17-feature order, class codes `[0, 1, 2]` as Lower/Middle/Higher, the ranking score `P(Higher)-P(Lower)`, selected `C=0.1`, development-only evidence, the 101,087-row training period and latest target end 2024-06-28, dependency versions, and source/contract/9.3 hashes. The rank score is not an expected percentage return. No Shariah result is included.

`fixture_input.json` contains one frozen AAPL feature row from 2024-05-30, with the exact feature order. `fixture_expected.json` stores probabilities `[0.3162217935279583, 0.36315921285394037, 0.3206189936181013]` and rank score `0.004397200090142994`. A separate Python process loaded the package and reproduced those probabilities within absolute tolerance `1e-12`. This is a serialization check, not a forecast-quality metric.

The builder/verifier is `src/model_training/phase9_return_package.py`. To verify the existing package without fitting, run from the repository root:

```powershell
.\.venv-phases\Scripts\python.exe -c "from pathlib import Path; from src.model_training.phase9_return_package import verify_return_package; print(verify_return_package(Path('reports/model_evaluation/phase9_return_package_v1')))"
```

This package is only for trusted local artifacts in the recorded Python/scikit-learn environment. Historical feature reconstruction and raw-bar validation belong to 9.6; prediction-output checks belong to 9.7. Source-quality limits and lack of untouched post-fit evaluation remain disclosed in the 9.3 repeat.
