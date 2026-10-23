# Phase 1 Execution Directives: Risk and Return Objectives

**Role:** Expert Quantitative Finance Coding Agent & Engineering Team
**Status:** Approved Specification for Phase 1 Experiments
**Objective:** Implement new relative-return classification and training-anchored risk classification models. Simultaneously preserve existing absolute-return regression and numerical risk models strictly as comparative benchmarks.

---

## 1. RETURN TASK: Same-Date Relative-Return Classification

**Shift in Focus:** Move from absolute percentage guessing to peer-relative ranking on the exact same date. 

### Target Definition
*   **Horizon:** Next 20 trading sessions (pre-close $t$ to close $t+20$).
*   **Universe:** Fixed 50-stock reference universe.
*   **Label Creation (Per Date):** For each date $t$, rank the 50 stocks by their actual 20-day forward return. Divide them into:
    *   `0`: Lower third (Bottom 33.3%)
    *   `1`: Middle third (Middle 33.3%)
    *   `2`: Higher third (Top 33.3%)
*   *Note:* Establish a strict tie-breaking policy in the code; do not arbitrarily split equal returns by ticker.

### Inference & Output
*   Model must output predicted class probabilities: `P(Lower)`, `P(Middle)`, `P(Higher)`.
*   **Ranking Score Formula:** Calculate the ordering score as `Score = P(Higher) - P(Lower)`.

### Evaluation Metrics
*   **Primary Metric:** Mean within-date **Spearman Rank Correlation** across chronological folds.
*   **Secondary Metrics:** Macro F1, Class Precision/Recall, Ordinal Error (mean absolute class distance using codes 0/1/2), Confusion Matrix.

---

## 2. RISK TASK: Training-Derived Volatility Bands

**Shift in Focus:** Maintain symmetric volatility as the risk unit, but classify into fixed, historically anchored bands rather than dynamic per-date sorting.

### Target Definition
*   **Quantity:** Annualized 20-session realized daily-return volatility.
*   **Label Creation (Pooled Training Data):** 
    1. Pool all eligible volatility outcomes across *only the training data*.
    2. Calculate the 1/3 and 2/3 quantiles to define the boundaries for `Low`, `Medium`, and `High` risk.
    3. **Freeze these boundaries** for the model version and apply them out-of-sample to validation/test sets. Do NOT recalculate boundaries per day.

### Evaluation Metrics
*   **Primary Metric:** **Macro F1**.
*   **Critical Failure Metric:** **High-risk outcomes predicted as Low** (Must be heavily monitored).
*   **Secondary Metrics:** High-risk Precision/Recall, Ordinal Error, Log-loss / Brier score (for probability calibration).

---

## 3. CONTROLLED MODEL CANDIDATES & BENCHMARKS

You must build a parallel pipeline that runs the new experimental candidates against the preserved benchmarks.

### A. New Candidates (The Challengers)
1.  **Baseline Classifiers:** `LogisticRegression` and `HistGradientBoostingClassifier` for both return and risk categorical tasks.
2.  **Ordinal Classifier:** Implement an ordinal classifier if standard multiclass distances prove problematic (i.e., the model confuses "High" for "Low").
3.  **Listwise Ranker (Optional/Later):** `LGBMRanker` (LambdaMART). Use `group = date` to preserve contiguous date batches. Set relevance mapped to the future relative return tertiles.

### B. Preserved Benchmarks (The Baselines)
Run these alongside the new candidates on the exact same data splits:
1.  **Absolute-Return Regression:** Keep the existing numerical return prediction model (e.g., Ridge). Convert its output into a ranking and evaluate via Spearman.
2.  **SPY-Relative Classes:** Existing benchmark-relative models. 
3.  **Numerical Risk Forecast:** The existing continuous volatility prediction model, converted into the training-derived Low/Medium/High classes for direct comparison.
4.  **20-Day Momentum:** Standard trailing performance baseline.

---

## 4. STRICT DATA HYGIENE & ANTI-PATTERNS

The coding agent must strictly enforce the following rules:

*   **NO Data Leakage (Chronological Splits Only):** Do not use random or standard k-fold CV. Use strict chronological time-block validation.
*   **Purge Overlaps:** Ensure a 20-day gap (the horizon) between the end of the training data block and the start of the validation data block.
*   **NO Markowitz Injection:** Do not treat rank scores or classification probabilities as expected percentage returns. They must not be fed into standard Mean-Variance optimizers. They are preference vectors only.
*   **Correct Drawdown Formula:** If calculating drawdowns, do not use naive trailing peaks. Use the project-standard `drawdown_from_peak_60d`.
*   **NO Dynamic Risk Sorting:** Never sort stocks into Low/High risk based on the current day's distribution. Risk cutoffs must come from the training distribution.
```eof