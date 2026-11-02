# Source-code layout

- `api/` contains the FastAPI service boundary.
- `data_pipeline/` downloads, validates, cleans, and reconciles source data.
- `feature_engineering/` creates historical market features.
- `target_engineering/` creates future outcomes, labels, and model-ready rows.
- `model_training/` defines chronological evaluation, trains candidates, and
  builds model-comparison reports. Its `feature_ablation/` subpackage contains
  the Phase 6 contract and inventory tools called by the student-run notebook.
- `legacy/` preserves earlier research workflows and benchmark code.

The repository-level `data/` directory stores datasets. The
`src/data_pipeline/` package stores code that operates on those datasets.
