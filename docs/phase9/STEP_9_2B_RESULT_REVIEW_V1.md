# Phase 9.2b: Student-run development result review

Reviewed the student's `phase9_tuning_v1.zip` without rerunning fitting. ZIP
SHA-256: `ca0a3d0946914b78a038d195ac22a9e7aca919ff2d9b5caf07ecdb9570bc6e6d`.
It contains the five expected files: input identity manifest, eight fold-role
records, 76 candidate/fold records, outer predictions, and a selection-review
placeholder. The dataset, fold protocol, Phase 7 experiment contract, and
candidate-report hashes in the manifest match the recorded identities. The
runner hash `28882ae0868d318b9edd2e529074a6b35ff33f318d13d8bc661539a3fdb039ec`
matches Git `HEAD` of `src/model_training/phase9_experiment.py` at review time;
the later working-tree version is different. The contract hash matches the
current `configs/phase9_experiment_protocol_v1.json`.

| Task/factor | Mean primary metric | Difference from rerun baseline | Improving folds |
| --- | ---: | ---: | ---: |
| Return baseline | 0.033858 Spearman | 0 | 0/4 |
| Return class weighting | 0.033560 | -0.000299 | 0/4 |
| Return no scaling | 0.031347 | -0.002511 | 0/4 |
| Return original 14 features | 0.032457 | -0.001402 | 2/4 |
| Return remove 20-day momentum | 0.033940 | +0.000082 | 2/4 |
| Return peer z-score | 0.034489 | +0.000631 | 1/4 |
| Return sigmoid calibration | 0.026600 | -0.007259 | 1/4 |
| Risk baseline | 0.571969 macro F1 | 0 | 0/4 |
| Risk learning rate | 0.575893 | +0.003924 | 2/4 |
| Risk iterations | 0.569536 | -0.002434 | 0/4 |
| Risk leaf nodes | 0.571969 | 0 | 0/4 |
| Risk minimum leaf size | 0.571807 | -0.000163 | 1/4 |
| Risk L2 | 0.573043 | +0.001073 | 2/4 |
| Risk remove SMA50 | 0.572631 | +0.000662 | 2/4 |
| Risk remove 60-day volatility | 0.568557 | -0.003412 | 0/4 |
| Risk chronological iteration variant | 0.568270 | -0.003699 | 2/4 |

The return `C` factors selected the same baseline in every fold. None of the
tested changes met the predeclared three-of-four-fold primary-metric gate.
No tuned candidate should be promoted from this run.

## Reproducibility and protocol limitations

1. The rerun risk baseline mean macro F1 is `0.571969`, while the frozen Phase 7
   candidate report says `0.570616`. Fold-level values differ despite matching
   input identities and leaf-node settings. The output manifest does not record
   Python/scikit-learn versions, so dependency differences remain a possible
   explanation, not a demonstrated cause. The student later reported Colab
   Python 3.13.18, NumPy 2.1.3, pandas 2.2.3, and scikit-learn 1.6.1;
   whether that was the uninterrupted runtime that produced the ZIP was not
   established. The difference is small and does not alter candidate selection.
   Preserve it as a reproducibility limitation, not a 9.2c blocker.
2. The implementation labelled `chronological_early_stopping` selects the
   iteration count on the tuning block and scores the later block without using
   it to choose the stop point. That differs from the written protocol's later
   stop-block rule. Treat this variant as a diagnostic only until corrected and
   rerun by the student. Exclude it from selection; a rerun is needed only if
   the team later wants to promote this specific variant.
3. The bundled `selection_review.md` is a generic instruction, not a measured
   selection decision. The table above is a descriptive review of the reported
   metrics; a complete 9.2c decision must also inspect probability quality,
   High-risk recall, High-to-Low errors, and per-fold failures.
4. The four outer folds are reused development periods. The already viewed
   2026 benchmark evaluation does not validate these changed AI models.

No result file was extracted over existing evidence, no model was fitted by
Codex, and no final candidate was selected here.
