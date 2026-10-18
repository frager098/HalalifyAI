# One table, six targets (Risk, Absolute Return, and Excess Return Alpha)

Use model_dataset.csv for risk, nominal return, and excess return (alpha) regression and classification. All six targets and all future-window metadata are excluded from feature_columns in targets_metadata.json. Select the desired target as y; never include any target in X. Use dataset_split to select train, validation and test rows. Exclude purged and unlabeled rows. Null targets mean insufficient complete future returns.

Targets:
1. risk_volatility_next_20d: Annualized next-20-session realized volatility (regression).
2. risk_class_next_20d: Low/medium/high realized volatility (classification).
3. return_next_20d: Next-20-session price return P[t+20]/P[t] - 1 (regression).
4. return_class_next_20d: Low/medium/high price return (classification).
5. excess_return_next_20d: Next-20-session excess return over SPY benchmark (regression, alpha).
6. excess_return_class_next_20d: Low/medium/high excess return relative to market (classification, alpha).

Classes use training-only pooled tertiles with fixed thresholds. SPY is a benchmark feature, not a modeled company. Targets use future data intentionally; features must not. Rows assume prediction after the current close. The source's unresolved corporate-action and historical identity checks remain applicable.
