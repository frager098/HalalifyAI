# Phase 8 documents

Phase 8 evaluated the frozen Phase 7 procedures on the reserved period from 2026-01-02 through 2026-09-30. Read these documents in order:

1. [Data collection](DATA_COLLECTION.md) — provider extraction and later-period source data.
2. [Evaluation contract](EVALUATION_CONTRACT.md) — dates, inputs, outcomes, cutoffs, and frozen evaluation rules.
3. [Dataset and notebook runbook](DATASET_AND_NOTEBOOK_RUNBOOK.md) — preparation, validation, Colab upload, and result download instructions.
4. [Final conclusion](FINAL_CONCLUSION.md) — observed results, limitations, artifact hashes, and Phase 9 gate.
5. [Phase tracker](../Phases.md#phase-8--evaluate-on-a-reserved-later-period) — completed step checklist.

Machine-readable contracts are `configs/phase8_evaluation_contract_v1.json`, `configs/phase8_procedure_freeze_v1.json`, and `configs/phase8_review_v1.json`. The one-time evaluation and review evidence is under `reports/model_evaluation/phase8_reserved_evaluation_v1/`; generated reports may be available only locally because that directory is Git-ignored.

The 2026 evaluation was performed once. Do not rerun it to change the retained procedures; a changed approach requires another future period for a new untouched evaluation.
