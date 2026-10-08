# Training data repair

Reviewed on 2026-10-08. The original model notebook at feature/model-pipeline-prototype commit 6c417db continued after failed action collection and price audits, and set absent return_transition_verified and share_basis_verified fields to True. Its saved execution confirms that path was used. This invalidates the claim that all training prices passed those checks; it does not establish how much the defect caused poor prediction scores.

The repaired module src/data/training_inputs.py requires explicit, correctly parsed verification flags and a separate SPY series. Its preparation command binds explicit price, raw-reference and action inputs, verifies retained response hashes and completion statuses, performs numerical reconciliation, and writes a new audited output and source manifest. Unverified rows remain in the audit; affected historical feature and future target windows are excluded. It does not certify completeness of all corporate actions or issuer identities.

The repaired notebook notebooks/HalalifyAI_Audited_Risk_Return_v2.ipynb defaults to uploading audited_prices.csv. In API mode it explicitly collects the raw reference, stops on failures, identifies the action folder created by that run, and uses the resulting audited CSV. It rejects prebuilt feature matrices for this repaired experiment so calculations must be rebuilt. Saved old output cells were cleared. The notebook code cells were syntax checked, but the complete Colab/API/ONNX run has not been executed here.

The notebook now permits the linear/logistic baseline to win validation selection and includes mean/majority and historical baselines in retrospective final reporting. The 2023-2025 test period was already inspected in the original experiment: repeated results cannot be described as a newly untouched holdout. Do not retune against that period or promise highest accuracy. A future methodology extension needs registered development-only validation and an honest independent evaluation plan.

Dataset exclusions now retain feature-window reasons rather than blank explanations. The current proposed v1.1 reference uses 50 companies plus SPY and early-2016 warm-up. Do not silently replace it with the older 40-stock/2015 reference or expand to all Kaggle constituents. Shariah screening remains a separate evidence and approval task.

Use the explicit command below only with the matching retained source files, then pass the printed audited output to build_research_dataset. Never set evidence flags True manually.

```text
python -m src.data.training_inputs --prices PATH_TO_DUAL_BASIS_CSV --raw PATH_TO_RAW_REFERENCE_CSV --actions PATH_TO_ACTION_FOLDER --repo .
python -m src.data.build_research_dataset --prices PATH_PRINTED_BY_AUDIT --repo .
```

Legacy retained raw-reference metadata did not include a completion status or normalized CSV checksum. In this review, a separate new reference snapshot was derived only after validating all original page hashes, terminal pagination and exact reconstructed CSV values. The original metadata and data were preserved. Do not make the new validation gate accept missing status implicitly.

The newer Colab input has SHA256 7726381a459599eb5bf8e3ee5aa202a74cdb26fa4a2b2e3bad69a5a1d070b0f3. It is not committed on GitHub and was not found in the local price-snapshot folder. The present reproduction uses the earlier retained source snapshot; it cannot establish an exact score change against the newer run. Obtain that exact daily_prices.csv and its raw collection evidence for a matched comparison. API credentials must not be shared.

Original user project and GitHub branches remain unchanged by this isolated preparation. The repair branch is feature/training-data-repair based on develop, with the existing unmerged integrate-data-processing dependency history explicitly merged locally. No peer approval, release, deployment or Shariah approval is claimed.

Executed evidence: 59 tests passed in the existing isolated Python 3.12 environment, one upstream deprecation warning. Original response reconstruction and price audit reproduced the prior audited CSV hash exactly. Research rows: 118,643, split into 58,157 train, 24,150 validation and 36,336 test. All 22 documented classifier fits were rerun using train/validation only. Selected return validation accuracy 36.882%, macro-F1 0.362892; selected risk validation accuracy 60.675%, macro-F1 0.577060. These reproduce earlier provisional results; they are not improved final-test claims. The full repaired Colab/API/ONNX notebook and fresh dependency installation were not run. Publish/install the repair branch before using its GitHub-cloning Colab setup; it is currently local only.

## Retrospective training review, 2026-10-08

Current executed classification results and limits are in [audited_training_results.md](audited_training_results.md). The frozen return/risk classifiers were refitted and evaluated retrospectively on 2023-2025; older statements that test evaluation is pending are superseded for these two classifiers only. No independent new holdout, regression re-evaluation, calibration, backtest or Shariah approval is claimed. All 62 tests pass in the existing isolated Python 3.12 environment.

