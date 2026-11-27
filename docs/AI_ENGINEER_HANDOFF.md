# HalalifyAI: request for an AI engineer's advice

I am building HalalifyAI, a software product intended to help users compare and select U.S. stocks using predictions of future return potential and price risk. Shariah screening is a separate rule-based component; only stocks that pass an approved screen may enter a recommended portfolio. The first implementation uses a fixed research universe of 50 stocks. This is my FYP, and I have about one week for the next major development step. I would value a practical recommendation that can produce a usable model and an honest evaluation within that time.

## Exact prediction tasks

- **Return:** At the close of trading session `t`, rank eligible stocks by their *relative* return over the next 20 trading sessions. The approved target divides same-date future returns into Lower, Middle, and Higher groups. The approved classifier output is `P(Lower)`, `P(Middle)`, and `P(Higher)`; the ranking score is `P(Higher) - P(Lower)`. Mean within-date Spearman correlation is the primary research metric. A rank score is not a forecast percentage return.
- **Risk:** Predict the next 20 sessions' annualized realized volatility, or its Low/Medium/High class. Class boundaries come from training outcomes only and are held fixed during evaluation. Macro F1 is primary; actual High-risk cases predicted Low are a critical error. If a model emits probabilities, they need evaluation rather than being assumed calibrated.
- **Timing:** Every input must have been available by the prediction date. Training and evaluation are chronological with a purge for overlapping 20-session targets. User risk preference belongs in later portfolio construction, not in changing the model's class meanings.

## Data and implementation already available

We have collected, cleaned, and validated daily market data; engineered market features; constructed 20-session future return and volatility labels; and built a reproducible chronological evaluation pipeline. The approved Phase 8 reserved dataset has 9,350 eligible company-date rows across 187 sessions from 2026-01-02 to 2026-09-30, with 50 companies per session. The project has reusable code under `src/`, student-run notebooks, frozen contracts under `configs/`, and saved experiment results under `reports/model_evaluation/`.

Phase 7 trained Logistic Regression and HistGradientBoosting classifiers using the approved market feature sets and four chronological development folds. Phase 6 investigated feature groups, but validated point-in-time SEC fundamentals were not ready for use as model predictors. The 50-stock universe has selection and survivorship bias. Some corporate-action magnitudes remain independently unverified. We do not yet have a verified historical, timestamped stock-news dataset for sentiment.

Key files if you want technical detail: `AGENTS.md` (project context), `docs/Approved phases specifications.md` (approved prediction tasks), `docs/Phases.md` (progress), `configs/phase7_model_freeze_v1.json` (selection rules), `docs/PHASE7_REPORT.md` (development decision), and `docs/phase8/FINAL_CONCLUSION.md` (reserved results and artifact hashes).

## The problem blocking the existing Phase 9 plan

The Phase 7 selection rules required learned return candidates to beat the momentum benchmark on mean daily Spearman and in at least three of four folds. Learned return candidates had higher **average** scores than momentum, but each beat it in only two folds. For example, the Logistic Regression candidate averaged `0.033858` versus momentum's `0.000577` in development, yet passed only two folds. This suggests unstable improvement; it does **not** prove that the data is incorrectly cleaned or that learned models cannot help.

The risk candidates also improved average macro F1 over trailing volatility but failed one or more predeclared safety requirements. For example, the HistGradientBoosting candidate averaged `0.570616` versus `0.532599` for the benchmark and improved in all four folds, but its mean High-risk recall was lower (`0.632726` versus `0.656862`). Logistic Regression candidates either worsened High-risk recall or increased serious High-to-Low errors. Consequently, the frozen selections are the simple `momentum_20d` return ranker and trailing `volatility_20d` risk bands, not fitted ML models.

The one-time reserved Phase 8 evaluation scored **those simple selections**, not the rejected learned candidates. Return mean daily Spearman was `0.013061`; risk macro F1 was `0.553678`, High-risk recall `0.732300`, and Low-risk recall `0.394467`. These numbers are limited evidence for those controls, not evidence that a new model works. Phase 9 currently says “save models and verify inference,” but there is no selected fitted model artifact or approved return-class probability output to save.

## My idea: use a pretrained model if it helps

I am considering a pretrained financial time-series model, such as Kronos, or a general time-series foundation model such as Chronos/TimesFM, to reduce training time. I am also open to fitting a purpose-built same-date ranker (for example LambdaMART) for returns and a future-volatility model (for example a daily-data HAR-style model) for risk. These are **ideas to assess**, not verified improvements. Pretrained price forecasts do not automatically satisfy my 20-session ranking/class-probability or risk-class requirements. A model pretrained on historical market data may also have seen a period we want to use for evaluation; please assess that before recommending an untouched-test claim. FinBERT would supply sentiment from historical news, not directly predict our targets, and we currently lack a validated historical news feed.

The January–September 2026 outcomes have already been viewed. A changed model cannot be presented as freshly tested on that same period. If a new later period with complete 20-session labels is unavailable, we should report development-only evaluation transparently rather than invent an independent test.

## What I need from you

1. Which **one return approach and one risk approach** would you choose for this exact dataset and one-week deadline? Would you use a pretrained checkpoint, train on our data, or combine both? Please name the smallest credible implementation path and a fallback if a dependency fails.
2. Can the chosen return approach provide the approved three class probabilities and a same-date ranking score? If it only produces ranking scores, what honest output contract would you recommend? Can the risk approach produce the approved risk classes and, if needed, evaluated probabilities?
3. What are the most likely causes of the four-fold inconsistency and serious risk errors, and which **small diagnostic** would distinguish weak features from a flawed target, data problem, or unstable model?
4. How would you validate the new approach without reusing the viewed 2026 period as an untouched test? What minimum evidence would justify showing its outputs to users, and what limits should the interface display?
5. What should we cut from this week's scope to finish a working end-to-end stock-ranking and risk-prediction flow? Please flag any claim or dependency in the proposed approach that you cannot verify.

I am looking for a concrete engineering recommendation, not a promise of high accuracy. The software should provide useful, clearly explained outputs, and any quality claim should match the evidence we actually obtain.
