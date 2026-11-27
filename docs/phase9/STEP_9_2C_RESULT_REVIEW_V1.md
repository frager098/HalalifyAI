# Phase 9.2c student-run final-fit review

The student ran `notebooks/phase9_final_fit.ipynb` locally. This review reads
the resulting `reports/model_evaluation/phase9_final_fit_v1/manifest.json`
and model files; it does not refit or score the models. The manifest records
Python 3.12.10, NumPy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, SciPy 1.18.1,
and joblib 1.6.0. It identifies the result as **development only**.

## Identity and artifact checks

All seven input hashes, the final-fit contract hash, and all three code hashes
match the current files. Both model-file hashes match the manifest. The
return file loads as a `StandardScaler` → `LogisticRegression` pipeline with
17 features, classes `[0, 1, 2]`, `C=0.1`, and a scaler fitted on 101,087
rows. The risk file loads as `HistGradientBoostingClassifier` with seven
features, classes `[0, 1, 2]`, 100 iterations, 31 maximum leaf nodes, learning
rate 0.1, minimum leaf size 20, L2 0, and automatic early stopping disabled.

| Artifact | SHA-256 |
| --- | --- |
| Return model | `e7c0e21f644363f069ffd9d52a2bf0c299fed7cd043e80ba844779ae700d401c` |
| Risk model | `5e05f753e21fbbe3c528f5e6d25707ee9080cb61a91afcbd3826ec7258465fae` |

## Chronology and row accounting

Independent read-only filtering of the frozen 124,987-row Phase 6 dataset
reproduced the manifest's row-key hashes, date ranges, class counts, and
training-only risk quantiles. There are no duplicate ticker/date keys or
nonfinite values in the selected features of any fitted role.

| Role, each task | Rows | Sessions | First feature date | Last feature date | Latest target end |
| --- | ---: | ---: | --- | --- | --- |
| Inner training | 83,187 | 1,678 | 2016-03-31 | 2022-11-25 | 2022-12-23 |
| Inner validation | 5,250 | 105 | 2022-12-28 | 2023-05-30 | 2023-06-28 |
| Final refit | 101,087 | 2,036 | 2016-03-31 | 2024-05-30 | 2024-06-28 |

The inner training labels end before the first validation feature date
(2022-12-23 < 2022-12-28). The scheduled validation interval was
2022-12-27–2023-06-28; eligibility and the target purge leave the observed
dates shown above. The final refit requires both feature date and target end
to be strictly before 2024-07-01. Final rows comprise 83,237 `train` and
17,850 `validation` rows, **zero `reused_test` rows**, and all 50 tickers.
Every final date has 49–50 eligible peers, above the frozen 45-peer minimum.
Per-ticker final row counts range from 1,323 to 2,036; coverage is not
uniform across the 50 stocks.

The 106,087 source rows with session dates before 2024-07-01 reduce as
follows: 1,000 have target windows crossing the cutoff; a further 3,000 have
`feature_warmup_or_missing` and 1,000 have the frozen `purged_window`
ineligibility flag. This leaves **101,087** eligible rows per task. Keeping
the earlier development-boundary purge excludes those 1,000 rows even though
their target ends precede 2024-07-01; this is conservative and follows the
frozen `eligible_only` contract. The return and risk eligibility flags match
on these knowable rows.

Return final-fit class counts are 32,561 Lower, 33,934 Middle, and 34,592
Higher. Risk cutoffs recalculated from final-fit training rows only are
0.18147671306250138 and 0.27948690312156266. They yield 33,696 Low,
33,695 Medium, and 33,696 High rows, matching the manifest exactly. These
are target-class cutoffs, not Shariah thresholds.

## Selection scores and interpretation

The frozen fourth inner validation chose return `C=0.1`: mean daily Spearman
was 0.162126 versus 0.162061 (`C=1`) and 0.162058 (`C=10`). It chose risk
31 leaf nodes: macro F1 was 0.611874 versus 0.609870 (15) and 0.597153
(63). These scores and selected settings exactly match the original Phase 7
fourth-fold inner-candidate report in the recorded local environment.

These are **selection-block scores**, not performance scores for the newly
refitted 101,087-row models. The notebook did not produce independent
post-fit validation or test metrics. Earlier Phase 7 outer-fold evidence is
mixed: return ranking had negative Spearman in folds 2 and 4, and the risk
model's High recall in outer fold 4 was about 0.503. The fitted models are
therefore research artifacts, not demonstrated reliable forecasts.

## Remaining gates

Step 9.2c's two trained AI artifacts and their provenance are present. Step
9.3 must now be repeated against these selected inputs before packaging.
The inference contract is still draft, and the old stopped 9.3 report remains
historical evidence. The Phase 6 feature-freeze hash mismatch is still
unresolved. The dataset metadata says `ready_for_training: false`; this
research fit does not override its source-quality and reused-test warnings.
The manifest's artifact paths use Windows separators from the student's local
run; consumers on another OS should resolve the two filenames relative to
the versioned output directory and verify their hashes, rather than treating
those strings as portable paths.
