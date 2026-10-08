# Provisional validation evaluation

2026-10-08 reproduction: all22 documented candidate fits rerun after strict input-gate repair. Selected return validation accuracy36.882%, macro-F1 .362892; selected risk60.675%, .577060. Earlier retained audited data reproduced exactly. This is not an accuracy improvement or new untouched-test claim. See training_data_repair.md for the original notebook's confirmed audit bypass and the unavailable newer input.

Executed 2026-10-02 on the reconciled price-only research dataset. Models fit 58,157 training rows and were compared on the same 24,150 validation rows. **Test performance has not been calculated.** These are academic preliminary results, not a financial or screening approval.

Macro-F1 averages how well a model identifies each of the three classes. It is not the percentage of predictions that are correct. Higher is better; the detailed reports also give accuracy, balanced accuracy, per-class results, confusion matrices and log loss.

| Target | Selected model | Validation macro-F1 | Previous-20-session baseline | Majority baseline |
| --- | --- | ---: | ---: | ---: |
| Return class | Logistic regression, C=1 | 0.362892 | 0.324436 | 0.197169 |
| Volatility class | Random forest, 300 trees, depth 6, minimum leaf 20 | 0.577060 | 0.549110 | 0.086235 |

Eleven configurations per target were compared: three logistic regressions, four random forests and four histogram gradient boosting classifiers. Seed 42 was fixed. Return HGB achieved 0.369334, but its advantage over logistic regression was below the predefined 0.01 tie margin, so the simpler family was selected. Risk random forest had the best score and no simpler-family candidate within that margin.

Models are currently fitted on initial training rows only. Training-fitted feature scaling is inside the logistic-regression pipeline. Thresholds were fitted only on training targets. Date-boundary label purges prevent training targets reaching validation and validation targets reaching test. No future targets enter the 16 features.

In a fresh Python 3.12 virtual environment, 35 tests passed and `pip check` found no broken requirements. The full rebuilt dataset matched exactly, and refitting the two selected configurations reproduced validation probabilities within 1e-12 and macro-F1. The complete 22-candidate grid was not rerun in the fresh environment. One Starlette test-client deprecation warning does not change the passing checks. Installed versions are saved with the verification report.

The five unsupported spin-off transitions and incomplete windows are excluded. Classes can be imbalanced across years; no significance test or guarantee of useful live performance is claimed. Probabilities are uncalibrated. Methodology acceptance, final refit, untouched-test evaluation, screening evidence and portfolio backtesting remain pending.

## Retrospective training review, 2026-10-08

Current executed classification results and limits are in [audited_training_results.md](audited_training_results.md). The frozen return/risk classifiers were refitted and evaluated retrospectively on 2023-2025; older statements that test evaluation is pending are superseded for these two classifiers only. No independent new holdout, regression re-evaluation, calibration, backtest or Shariah approval is claimed. All 62 tests pass in the existing isolated Python 3.12 environment.

