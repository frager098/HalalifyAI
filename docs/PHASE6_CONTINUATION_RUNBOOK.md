# Phase 6 rerun from the student's Phase 5 dataset

## Experiment boundary

This rerun continues the exact artifacts used in the student's completed Phase
5 work. It is a new experiment named `phase6_phase5_continuation_v1`. It does
not overwrite or reinterpret the friend's `phase6_recovery_v1` experiment.

Frozen inputs:

- Dataset: `data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv`
- Dataset SHA-256: `71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f`
- Metadata: `data/processed/model_inputs/market_features_and_labels_v1/dataset_metadata.json`
- Metadata SHA-256: `b36ed46ac5a68b74130b26df8f20d965928c53d62467c163a214f8b37fd35ba9`
- Reproduced protocol SHA-256: `048d82ce2ed0bedde60bd5f6215303fa86ebdab31aae5b5c330f0947372859ff`

## Colab execution order

Use one fresh CPU runtime. Open each notebook from the pushed
`feature/model-evaluation` branch and run every cell from top to bottom:

1. `notebooks/phase6_phase5_continuation_setup.ipynb`
2. `notebooks/phase6_momentum_ablation.ipynb`
3. `notebooks/phase6_volatility_ablation.ipynb`
4. `notebooks/phase6_downside_trend_ablation.ipynb`
5. `notebooks/phase6_market_relative_ablation.ipynb`
6. `notebooks/phase6_volume_ablation.ipynb`

The first notebook clones the repository, restores the Git-ignored Phase 5 CSV,
checks its identity, reproduces the protocol, creates the feature inventory,
and validates the runner without fitting a model. The following notebooks fit
the five controlled ablation comparisons. Do not delete or rename an output
folder while its notebook is running.

If dependency installation changes packages already loaded by Colab, restart
the session once, rerun the setup notebook, and then continue in order.

## Expected outputs

All new outputs are created beneath:

`reports/model_evaluation/phase6_phase5_continuation_v1/`

The folder should contain:

- `chronological_evaluation_protocol.json`
- `feature_inventory.json` and `feature_inventory.csv`
- `runner_validation.json`
- `momentum_ablation/`
- `volatility_ablation/`
- `downside_trend_ablation/`
- `market_relative_ablation/`
- `volume_ablation/`

Each fitting notebook refuses to overwrite its own output directory. A refusal
means that evidence already exists in the current runtime; inspect or download
it rather than deleting it blindly.

## Save the reports before closing Colab

Run this final Colab cell after all six notebooks finish:

```python
import shutil
from google.colab import files

archive = shutil.make_archive(
    "/content/phase6_phase5_continuation_v1",
    "zip",
    "/content/HalalifyAI/reports/model_evaluation",
    "phase6_phase5_continuation_v1",
)
files.download(archive)
```

Keep the downloaded ZIP as local experiment evidence. Generated reports remain
Git-ignored; source code, notebooks, configuration, tests, and reviewed summary
decisions are the files intended for normal Git history.

## Phase 7 gate

Do not reuse `configs/phase6_feature_freeze_v1.json` automatically because it
belongs to the friend's recovery dataset. Review the five continuation summaries
first, then create a separately versioned continuation feature freeze for Phase
7 based only on these new results.
