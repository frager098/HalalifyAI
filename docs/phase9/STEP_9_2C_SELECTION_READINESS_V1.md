# Phase 9.2c selection and fit readiness

Status: **candidate families selected; final fitting pending**. This review uses the
student's original `phase9_tuning_v1.zip` and the extracted reports. It does
not create or claim trained model artifacts.

## What the development folds support

The frozen 9.2a rule requires improvement in at least three of four matched
outer folds. None of the 9.2b changes met that rule. The selected model
families are therefore the Phase 7 learned candidates: Logistic Regression with its
17-feature StandardScaler pipeline for return, and HistGradientBoosting with
its seven features for risk. The return class probabilities remain
uncalibrated. The risk early-stopping result is excluded because its code
selected iterations on the earlier tuning block instead of the designated
later stop block.

The return baseline's daily Spearman values were 0.097576, -0.021675,
0.115007, and -0.055475 across folds 1–4. The two negative folds show that
the ranking is unstable; mean 0.033858 is a development average, not an
expected live correlation. Sigmoid calibration raised mean multiclass Brier
and log loss and lowered mean rank correlation. It is not selected.

The risk rerun baseline's macro F1 values were 0.519433, 0.562399,
0.618402, and 0.587643. Its High-class recall was 0.665505, 0.619431,
0.750381, and 0.502261, with 241, 409, 142, and 274 High-to-Low errors.
The fourth fold's High recall is a material limitation. The lower learning
rate improved macro F1 only in folds 2 and 3, and raised High-to-Low errors
in fold 3 from 142 to 149. L2 improved macro F1 only in folds 2 and 4,
while fold 4 High recall fell from 0.502261 to 0.499246. Neither passes the
predeclared promotion and safety gates.

## Environment and reproducibility limitation

The risk baseline in this rerun averages 0.571969 macro F1; the frozen Phase
7 candidate report averages 0.570616. The report records Python 3.12.10,
pandas 3.0.6, NumPy 2.5.3, and scikit-learn 1.9.1. The 9.2b manifest records
input and code hashes but omits library versions. The student later reported
Colab Python 3.13.18, NumPy 2.1.3, pandas 2.2.3, and scikit-learn 1.6.1;
whether this was the uninterrupted runtime that produced the ZIP is unknown.
It is therefore not yet
possible to attribute the difference to versions, row selection, cutoffs,
model settings, or another cause. Identical dataset and protocol hashes alone
do not prove identical fitted predictions. The Phase 6 feature-freeze hash
also differs from the Phase 7 recorded identity, as noted in the 9.3 report.

A read-only check of the frozen dataset and each frozen outer training role
recalculated the four risk tertile pairs. They matched the recorded Phase 7
boundaries exactly: (0.1611244261, 0.2532609798), (0.1714205957,
0.2669263426), (0.1768120016, 0.2768403955), and (0.1831165703,
0.2848551206). Different risk cutoffs are therefore not the observed cause.

The student judged this small difference immaterial to the model choice. It
does not change any three-of-four-fold promotion outcome, so reconciliation
is not required before 9.2c fitting. Do not attribute it to Colab as a
proven cause or imply exact cross-environment reproducibility.

The frozen Phase 7 report and 9.2b ZIP must remain unchanged. A later
controlled rerun may investigate the baseline difference, but it is optional
for the present selection. Correct and rerun early stopping only if that
variant is considered for promotion; otherwise it remains excluded.

## Frozen final fitting rule

Keep both original Phase 7 **AI** model families and feature sets. Choose Logistic Regression `C`
from `[0.1, 1.0, 10.0]` using only a frozen chronological inner validation
block and mean daily Spearman. Choose risk maximum leaf nodes from
`[15, 31, 63]` using only that block and macro F1. Preserve grid order on
ties. The frozen block is fold 4's **inner validation**, scheduled from
2022-12-27 through 2023-06-28. Its eligible rows actually run from
2022-12-28 through 2023-05-30 after the 20-session target purge. Its inner
training labels must end before the first eligible validation session. Then refit
each chosen model on eligible development rows with both `session_date` and
`target_window_end` strictly before 2024-07-01. This purge prevents the
final fit from consuming outcomes in the viewed later period. Calculate
final risk cutoffs from these final training rows only.

The executable contract is `configs/phase9_final_fit_v1.json`; the student
entry point is `notebooks/phase9_final_fit.ipynb`, calling
`src/model_training/phase9_final_fit.py`. The notebook saves feature and
class order, dates, row counts, selected settings, training-only cutoffs,
dependencies, input/code/contract hashes, and artifact hashes under the new
`reports/model_evaluation/phase9_final_fit_v1/` location. It refuses to
overwrite evidence. Codex prepared and syntax-checked these files but did
not execute fitting; the student's run is still required to complete 9.2c.

The four outer folds are reused development evidence. No result here is an
untouched test, a production guarantee, or a Shariah-screening outcome.
