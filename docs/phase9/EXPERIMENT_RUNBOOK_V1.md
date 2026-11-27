# Phase 9.2a experiment runbook

The frozen experiment plan is [`configs/phase9_experiment_protocol_v1.json`](../../configs/phase9_experiment_protocol_v1.json). It defines a new Phase 9 comparison; the earlier Phase 7/8 results and methods remain preserved. No notebook, model, or result has been produced by Step 9.2a.

## Identity investigation

`configs/phase6_feature_freeze_v2.json` hashes to `9f9999df278823f9d73b688439085a349d99c74ecd2eac377c0f72cde9c2b91a` in both the current worktree and Git `HEAD`. Its only reachable Git revision has the same hash. Phase 7 records `312ec2857625ab6d87c90bc1eb61f4a36d637c7255f8a1d86b861df3195c29dc`. The recorded file identity cannot be reproduced from this repository history. The exact source of the recorded value is unknown. Keep the old reports untouched, disclose this mismatch, and identify new experiments with the actual hashes of the dataset, code, and contract they read. This does not by itself prove that Phase 7 model scores are incorrect.

## How the comparison works

Use the four frozen chronological development folds. For each task, compare one proposed change at a time against the Phase 7 learned candidate on identical eligible ticker-date rows. Tune inside the earlier inner period. Where calibration or explicit early stopping is tested, divide the observed inner-validation dates after the first 63 dates, purge target windows between roles, and score on the later outer block. An automatic random early-stopping split is forbidden. If any role becomes too small or lacks a class after purging, record the candidate as infeasible; do not relax chronology.

Report per-fold return same-date Spearman, macro F1, probability log loss and Brier score; report per-fold risk macro F1, High recall, High-to-Low errors, and probability scores. Retain the Phase 7 learned candidate unless a change satisfies the predeclared consistency and safety rules in the JSON. The four outer blocks have been examined before, so the comparison supports development decisions only.

## Student run order after the notebook is implemented

1. Open `notebooks/phase9_tuning_comparison.ipynb` locally or upload it directly to Colab. Run the setup cell. Colab clones the existing branch at `/content/HalalifyAI`; if the new Phase 9 code is not in that clone, upload `phase9_code.zip` containing only `configs/phase9_experiment_protocol_v1.json` and `src/model_training/phase9_experiment.py` at those repository-relative paths. It then installs the notebook dependencies.
2. Run the preflight cell. It reads the versioned contract, Phase 6 dataset, frozen chronological protocol, Phase 7 experiment contract, and selected candidate reports; in Colab upload `phase9_tuning_inputs.zip` containing only the missing Git-ignored inputs at the repository-relative paths printed by the cell. It checks hashes and lists missing files before any fitting.
3. Run the fold-role and experiment cells in order. They read the verified inputs, enforce chronology and 20-session purges, fit candidates, and display fold results. Outputs go only under `reports/model_evaluation/phase9_tuning_v1/` and must refuse overwrite.
4. Run the review/export cell. It writes the input identity manifest, fold roles, predictions, metrics, and selection review, then downloads the report bundle in Colab. Save the bundle before ending the Colab session.

The notebook and reusable `src/` implementation are Step 9.2b work. Do not run a nonexistent notebook or treat this runbook as measured evidence.
