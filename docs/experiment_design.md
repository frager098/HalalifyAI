# Halalify: experiment design

Version: `1.1` | Revised: `2026-10-02` | Experiment ID: `HALALIFY_US_20D_V1_1`
> **Revision 1.1 reconciliation:** See [data_reconciliation.md](data_reconciliation.md), which takes precedence over conflicting v1.0 examples below. This is a proposed team-review amendment, not a fabricated approval or completed model experiment. Keep the actual 50-company cohort (`configs/universe.json`) and SPY separately; use Alpaca SIP for 2016-2025, with the first 60 complete sessions as warm-up. The original 50-stock table, 2015/Yahoo pilot instructions, and approximate 100,800-row estimate are historical proposal material, not active collection instructions. Use the next session after SEC filing as the conservative availability rule. Screening and portfolio methodology remain proposed until their required review.


Companion specification: [data_dictionary.md](data_dictionary.md).

**Execution status, 2026-10-02:** The proposed v1.1 price-only experiment now has implemented features/labels and 22 provisional train/validation model fits. See [data_readiness.md](data_readiness.md) and [evaluation_report.md](evaluation_report.md) for executed evidence and limitations. This does not approve the methodology. Test performance, final refit, backend agreement, Shariah standard selection and portfolio backtesting remain outstanding. Original walkthrough instructions below are proposal material; the execution guide takes precedence for current file paths and scope.

**Beginner reading route:** start with the decisions in section 2, the worked target explanation in section 7, and the Day 2 walkthrough in section 14. Then read dictionary sections 1, 6, 7 and 8. The remaining sections are reference material for implementation; you do not need to memorize every backend field today.

## 1. What we are building and why

Halalify will screen company activities and finances, classify a stock's future return and volatility, and use eligible stocks in an educational portfolio prototype. The initial research question is:

> Using information available after a US trading session, can simple machine-learning models classify a stock's return and volatility over the next 20 trading sessions better than simple historical baselines?

There are three different outputs:

1. **Screening result:** whether the available evidence passes a named, versioned set of business and financial rules. This is a calculation and evidence-review task.
2. **Return class:** low, medium, or high future 20-session total return relative to fixed training-period boundaries. This is a prediction.
3. **Risk class:** low, medium, or high future 20-session realized volatility relative to fixed training-period boundaries. This is a separate prediction. It measures price variability, not every investment risk.

High return class does not guarantee a profit. Low volatility class does not make a stock safe. A classifier's probability of a class is not a predicted percentage return.

The existing four-week plan is the scope anchor. The research papers help select candidate features and evaluate methods; they do not establish that any model or feature set will succeed on this dataset. The literature review covers studies mainly from 2000–2019 and counts how often techniques were used; popularity is not comparative proof. [S1, S2]

## 2. Decisions frozen for version 1

| Decision | Selected setting | Reason |
| --- | --- | --- |
| Market | US-listed, USD-denominated common equities on NYSE/Nasdaq | Matches the team's chosen initial market. |
| Universe | 50 company candidates in the versioned universe configuration plus separate SPY | Manageable data audit, with varied company activities. |
| Observation | One stock on one exchange session | A row has an unambiguous information cutoff. |
| Raw history | 2016-01-01 through 2025-12-31 | Observed Alpaca coverage starts in 2016; the first 60 sessions provide warm-up. |
| Model observation dates | 2016 onward through 2025-12-31, valid complete feature windows only | Fixed end date avoids a moving experiment. |
| Frequency | One regular-session daily abar | Avoids intraday complexity in the first four weeks. |
| Prediction time | After the session close, once the daily bar is available | Today's full daily bar is then a valid input. |
| Main horizon | Next 20 exchange trading sessions | Approximately a trading month and suitable for the portfolio prototype. |
| Primary targets | Future total return and future annualized realized volatility | Clearly defined numerical outcomes underlying the classes. |
| Primary modeling task | Two separate three-class classifiers | Preserves the agreed return/risk classification scope. |
| Core predictors | 16 fields in `core_v1` | Small, reproducible first feature set. |
| Main candidates | Logistic Regression, Random Forest, HistGradientBoosting | Includes a simple baseline and two nonlinear comparisons in scikit-learn. |
| Primary selection metric | Validation macro-F1, separately for each target | Weights the three classes equally. |
| Main price/return benchmark | SPY adjusted returns | A tradable broad-US-market proxy; not a Shariah eligibility recommendation. |
| Main portfolio comparator | Equal-weight portfolio of the same dated eligible stocks | Separates model selection value from the screening filter. |
| Experiment seed | 42 | Reproducibility, not evidence of robustness. |
| Main portfolio cadence | Every 20 exchange sessions | Exact cadence; different from literal calendar-month rebalancing. |

These are design choices, not discoveries from an experiment. Change them through a new experiment version and record the reason before examining test performance.

## 3. Selected universe: 50 company candidates

The exact symbols are versioned in `configs/universe.json`. These are research candidates, not certified compliant holdings. Broad study groups are diagnostic labels, not historical sector classifications.

| Study group | Symbols | Count |
| --- | --- | ---: |
| Technology and internet | AAPL, MSFT, NVDA, AMD, AVGO, ORCL, ADBE, CRM, CSCO, INTC, GOOGL, META, NFLX | 13 |
| Consumer discretionary | AMZN, TSLA, HD, LOW, NKE, SBUX, MCD | 7 |
| Consumer staples | COST, WMT, PG, KO, PEP | 5 |
| Healthcare | JNJ, LLY, ABBV, MRK, TMO, ABT, DHR | 7 |
| Industrials | CAT, DE, HON, UPS, UNP, GE | 6 |
| Energy | XOM, CVX, COP, SLB | 4 |
| Financial services | JPM, BAC, GS, MS, V, MA | 6 |
| Materials | LIN | 1 |
| Utilities | NEE | 1 |
| Total company candidates | SPY remains separate | 50 |

Verify issuer/share-class identity and corporate actions. In particular, a broad financial-services label does not establish the same business rule result for every company. Current group labels cannot replace dated historical activity evidence. Train forecasting on usable company records; report eligible-subset performance only where dated screening evidence exists. Portfolio inclusion requires reviewed passing evidence.

### Selection limitations and missing data

This is a deliberately selected contemporary cohort, not a representative historical investable universe. It omits delisted failures and contains survivorship and selection bias. Results apply to this cohort; do not claim general US-market performance or successful historical stock discovery. Both the Boogie experiment and our own study need this limitation. [S2]

Do not replace poorly performing tickers or drop a company because of its test outcomes. Before training, audit coverage without inspecting model performance. Investigate errors and document exclusions in a universe manifest. If material identity or data problems leave fewer than 30 usable candidates, publish an amended version before model selection. Otherwise retain missing-record counts and use only valid windows, with exclusions visible in every period. Missing data caused by suspensions or delisting must be investigated rather than silently treated as an ordinary random gap.

SPY is an additional benchmark instrument; it is not the 51st company candidate and is not an eligible portfolio holding by default. Its sponsor describes its objective as tracking the S&P 500's price and yield performance before expenses. [S10]

## 4. Time, horizon, and the information boundary

Use a pinned US exchange calendar and America/New_York session dates. Weekends and exchange holidays are not observations. Early closes are valid sessions. Store actual timestamps in UTC; never hard-code the Pakistan/US time difference because US daylight saving changes it. [S9]

Let `t` be the completed session used to form a prediction. A 20-session target uses session `t+20` on the exchange calendar, not the twentieth calendar day and not the twentieth non-missing row returned by a provider.

The following are different:

- **Frequency:** receive one bar per trading session.
- **Lookback:** use, for example, the previous 60 daily returns as inputs.
- **Forecast horizon:** predict the next 20 daily sessions.
- **Rebalancing cadence:** revise holdings every 20 sessions in the main simulation.

Twenty sessions is a defensible first choice, not a proven optimal horizon. Shorter horizons answer a faster-trading question; longer horizons yield fewer non-overlapping outcomes over the same history. An optional validation-only sensitivity check compares 5, 20, and 60 sessions with the same model family and period. Recompute labels, training thresholds, and purge lengths for each horizon. Do not claim the 20-session choice is supported by a study that only tested calendar months. Do not choose the winning horizon on the final test set.

### Close information and executable prices

The ML target below is close-to-close total return. A prediction based on today's final close cannot also be assumed to have traded at that same close. The economic simulation therefore executes at the **next session's close**, with costs. This one-session delay deliberately makes tradable performance different from the idealized forecast target. Keep both evaluation types separate; do not shift the labels silently to make simulated performance look better.

## 5. Data sources and an achievable collection plan

| Dataset | Selected route | Limit and implementation requirement |
| --- | --- | --- |
| Daily stock and SPY bars, adjusted close, actions | Alpaca SIP via versioned split-only and all-adjusted snapshots | Actual project provider. Preserve responses and metadata; check separate price bases and actions. Account access and historical coverage must be measured. [Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars) |
| Documented price-provider alternative | Alpha Vantage `TIME_SERIES_DAILY_ADJUSTED` | Documentation lists as-traded OHLCV, adjusted close, splits and dividends. The endpoint is premium; no paid access is assumed or purchased. Use only if the team already has suitable access, and create a new dataset version. [S5] |
| Financial reports and company identifiers | SEC EDGAR submissions, Company Facts, and original filings | SEC APIs are official and require no API key. Company Facts does not guarantee all business-segment or prohibited-income detail; inspect original notes when needed. [S6] |
| Optional macro experiment | FRED `VIXCLS` and `DGS3MO` | VIX is index points; the three-month Treasury yield is annual percent. Preserve release availability and vintage information. [S7] |
| Trading sessions | Exchange calendar checked against NYSE holiday/calendar documentation | Pin the calendar source/version and use session indexes for all windows. [S9] |
| Screening reference | MSCI Islamic Index Series methodology, May 2025, asset-denominator variant | Candidate reference for a deliberately defined academic rule profile, subject to domain review; not a claim of index replication. [S8] |

Use `python src/data/download_alpaca.py` to collect a versioned Alpaca SIP snapshot of the configured 50 companies plus SPY for 2016-2025. Collect split-only OHLCV separately from all-adjusted close, preserving requests and original pages. Use `python -m src.data.collect_action_evidence` for action evidence. Do not use a Yahoo pilot or splice Yahoo history into this version. See `data_reconciliation.md` for the revised warm-up rule and readiness limits.

### Day 3 availability check, before committing to a source

1. Download AAPL, JNJ, JPM and SPY through the proposed route; this small sample covers adjustment checks, financial retrieval, and a screening rejection case.
2. Confirm full requested date coverage, OHLCV, separate adjusted close and action records; retain raw responses, timestamps, request parameters and hashes.
3. Inspect at least one split event and one dividend event; verify no artificial split-sized return appears and no dividend is counted twice.
4. Resolve one company's CIK and read one 10-K and one 10-Q with their availability dates.
5. Attempt to locate revenue, assets, debt, cash, receivables, and prohibited/interest income evidence. Report genuinely unavailable fields as missing.
6. Record provider failures and licensing constraints. Use the documented alternative only through available authorized access; do not splice providers silently.

This check remains to be run. The design is ready for collection, but it is not a claim that all required fields are downloadable for free.

## 6. Data stages and the 16 core features

Separate five kinds of information:

| Stage | Example | Meaning |
| --- | --- | --- |
| Raw observation | A daily adjusted close or filed assets value | Retrieved evidence, retained unchanged. |
| Feature `X` | Previous 20-session return | Information available when predicting. |
| Future target `y` | Next 20-session return | Known later; used for training/evaluation only. |
| Prediction | Probabilities of low/medium/high | Model output for a particular date. |
| Screening evidence | A dated debt ratio and rule result | Separate eligibility calculation. |

The exact `core_v1` input order is:

```text
ret_1d
ret_5d
ret_20d
ret_60d
vol_20d
vol_60d
downside_dev_20d
max_drawdown_60d
price_sma20_ratio
price_sma50_ratio
rsi_14
volume_ratio_20d
log_dollar_volume_20d
beta_60d
market_ret_20d
market_vol_20d
```

All formulas, units, warm-up requirements and missing-value rules are in the companion dictionary. Historical percentage return already represents the chosen momentum measure; do not create duplicate `momentum_20d` and `ret_20d` inputs with identical formulas.

Ticker, date, static sector group, compliance status, labels, future dates, and model outputs are not core predictors. Numeric ticker codes create an arbitrary ordering and must not be used. Sector information is retained for diagnostics and allocation constraints.

Do not start with GDP, news, an LLM, hundreds of indicators, or a large neural network. Optional groups are added through named experiments after the core pipeline works:

- `core_plus_macro`: two lagged FRED fields, with availability and vintage checks.
- `core_plus_fundamentals`: four point-in-time ratios in the dictionary; only if timestamped coverage is adequate.

Evaluate optional groups on the same eligible validation rows as the core comparison, and also report their coverage. A different row population must not be mistaken for a feature improvement. Freeze the group before the final test. No source establishes that 16 is an optimal number; it is a manageable initial specification. [S1, S3]

## 7. Targets and class definitions

Let `P_t` be the validated adjusted close and `r_t = P_t / P_(t-1) - 1` the simple daily return. All calculations are within one stock and aligned to exchange sessions.

### Return target

```text
future_return_20d(t) = P_(t+20) / P_t - 1
```

This is a 20-session total-return proxy before trading costs and purification. It is neither annualized return nor excess return over a risk-free rate. A move from 100 to 108 gives `0.08`, displayed as `8%`.

### Risk target

```text
future_volatility_20d(t) = sample_std(r_(t+1), ..., r_(t+20), ddof=1) * sqrt(252)
```

The forecast window is 20 sessions. Multiplication by `sqrt(252)` only expresses the volatility on an annualized scale; it does not make this a one-year forecast. This target captures realized variability, including upward moves, rather than default risk or a probability of loss.

Use exactly 20 consecutive future session returns. Missing future prices make the affected target unavailable. The last 20 observation dates cannot have completed labels if the final raw bar is 2025-12-31. They can still be valid inference rows, but not supervised examples. Do not impute future outcomes.

### Fixed training-period tertiles

Calculate the 1/3 and 2/3 quantiles separately for return and volatility, using only retained initial training rows after purging and quality checks. Use pooled stock-date targets and linear quantile interpolation. Save the four numeric cutoffs; they cannot be honestly filled in before the data are processed.

```text
low:    y <= q_1_3
medium: q_1_3 < y <= q_2_3
high:   y > q_2_3
```

Use lowercase strings with class order `[low, medium, high]`. If two cutoffs are equal, halt and review the label design rather than generating empty classes silently. Thresholds stay fixed throughout validation and the final test; class frequencies may shift. The final development refit also retains these original label boundaries so the meanings remain comparable.

Tertiles describe outcomes relative to the training distribution. A high-return boundary can be negative, and medium is not synonymous with zero return. The dashboard must show the actual stored thresholds and the 20-session horizon. Do not invent universal 5% or 15% boundaries or call these classes investor suitability categories.

For classroom illustration only: if fitted return boundaries were -2% and +4%, an observed +8% outcome would be high. These example numbers are not the experiment's actual thresholds.

## 8. Chronological splits and overlapping outcomes

| Stage | Candidate feature dates | Use |
| --- | --- | --- |
| Warm-up | First 60 observed consecutive sessions per instrument | Features only; no invented 2015 prices. |
| Initial training | 2016–2020 | Fit class boundaries, preprocessing and candidate models. |
| Validation | 2021–2022 | Select model family and the limited hyperparameter choices. |
| Final test | 2023–2025 | One frozen evaluation protocol after all choices are locked. |

Dates are inclusive calendar bounds but only valid trading sessions become observations. Use the same date partition for every stock. A market day must not be in training for one company and validation for another.

**Purge overlapping label windows:** for any training partition followed by evaluation starting on `T`, require `label_end_date < T`. Exclude approximately the final 20 training feature dates. Apply the same rule to validation targets used for selection before the test starts. This prevents December training examples from borrowing January validation prices as answers.

The gap is in exchange sessions, not in rows of a stacked 50-stock table. Plain `TimeSeriesSplit(gap=20)` on stacked stock rows is insufficient: split unique dates and map them back to all stocks, or enforce the label-end rule explicitly. scikit-learn documents a sample-count gap, which needs this adaptation for panel data. [S11]

Fit scalers, imputers if used in extensions, feature selectors, and label cutoffs only inside the training portion. A rolling feature for a validation day may legitimately use older training prices, because those prices were already known. Scikit-learn's pipeline guidance explains why learned preprocessing must stay outside held-out data. [S12]

### Final refit and the test lock

After selection, refit each winning model and its preprocessing on 2016–2022 examples whose labels end before the first 2023 test date. Keep the original class thresholds. Fit and freeze comparator baselines on that same development set. Freeze model, feature list, sample rules, costs and portfolio settings before evaluating 2023–2025. The main test uses static models, not ongoing retraining.

Do not alter the method after seeing test results and report it as the same untouched test. Correcting a confirmed code error is allowed, but record what changed and disclose that the test was revisited. If the team has already inspected or tuned against 2023–2025, mark it as retrospective evaluation and use a separately registered future paper-trading period for further confirmation.

Daily 20-session outcomes overlap. Forty stocks also share market shocks. Actual sample counts must be measured after warm-up, coverage exclusions and boundary purges; stock-date rows are not independent observations.

## 9. Models, controls and bounded tuning

Train one return classifier and one risk classifier. A single multi-output model is not needed for version 1.

| Method | Return task | Risk task |
| --- | --- | --- |
| Class-frequency baseline | Predict initial training class frequencies; argmax for class | Same procedure for risk labels. |
| Historical baseline | Map `ret_20d` into fixed return classes | Map `vol_20d` into fixed risk classes. |
| Logistic Regression | StandardScaler + multinomial classifier | Separate pipeline with the same predictors. |
| Random Forest | Nonlinear tree ensemble | Separate fitted estimator. |
| HistGradientBoosting | Nonlinear boosting classifier | Separate fitted estimator. |

Do not promise an accuracy percentage. If the historical baseline remains best on validation, it is an acceptable selected model and a useful research result.

Use this bounded initial search, with equal-weight classes/samples and seed 42:

| Candidate | Fixed settings | Values to compare |
| --- | --- | --- |
| Logistic Regression | L2 penalty; `lbfgs`; `max_iter=2000`; standardize using training statistics | `C` in `[0.1, 1.0, 10.0]` |
| Random Forest | `n_estimators=300`; `max_features='sqrt'`; `class_weight=None` | `max_depth` in `[6, 12]`; `min_samples_leaf` in `[20, 50]` |
| HistGradientBoosting | `learning_rate=0.05`; `min_samples_leaf=30`; `l2_regularization=1.0`; `early_stopping=False` | `max_leaf_nodes` in `[7, 15]`; `max_iter` in `[100, 200]` |

This is 11 configurations per target, not an unrestricted search. Disable automatic internal early stopping in this version so it cannot create a random time-mixed validation subset; scikit-learn's documented default is automatic. [S13]

Select by validation macro-F1, report each validation year separately, and treat differences under 0.01 as practically tied for this initial design. For ties, prefer Logistic Regression, then Random Forest, then HistGradientBoosting. Keep all candidate results. Re-run selected stochastic settings at seeds 7 and 2024 as sensitivity checks; do not choose the best seed after inspection. The primary reported run remains seed 42.

MLP, SVM, XGBoost and LSTM are optional future comparisons, not simultaneous requirements. Regression with Ridge can be an explicitly separate extension if numeric return estimates become necessary. Classifying by binning a regression prediction is not assumed superior to direct classification; compare it on validation before adopting it.

## 10. Evaluation and success criteria

For both targets, report macro-F1, balanced accuracy, ordinary accuracy, precision/recall/F1 and sample count per class, and a confusion matrix in fixed class order. Compare against both baselines on identical rows. For models and the class-frequency baseline with probabilities, additionally report multiclass log loss and a class-probability calibration plot. Do not treat model scores as empirically calibrated probabilities without checking them. A deterministic historical classifier need not be given artificial 0/1 probabilities for log-loss comparison.

For macro-F1, explicitly supply all three labels and set undefined divisions to zero; keep the class support counts beside the result. An absent class in a small slice limits interpretation. Balanced accuracy is mean recall over the classes present in that slice; do not compare small slices without their supports. No SMOTE or random resampling across time partitions is part of this design.

Slice results by year, ticker and study group, with sample counts. Report core feature coverage, prediction coverage, missing labels and excluded windows. Low coverage can hide difficult periods.

Because horizons overlap, report both:

1. Daily-observation metrics, clearly identified as correlated observations.
2. Metrics at non-overlapping 20-session anchors starting from the first date of each evaluation partition, using all available stocks on each anchor.

For uncertainty estimates, use 1,000 moving-block bootstrap samples with 20-session blocks, resampling the same date blocks for all stocks together. Show a 60-session block sensitivity if making a strong improvement claim. Do not use an independent-row bootstrap or a naive significance test that treats stocks/dates as independent.

A model is **useful in this sample** if it improves on the stronger baseline on validation and retains improvement on the frozen test with reasonable year-to-year stability. Report uncertainty and avoid a universal superiority claim. No improvement is a valid experimental outcome. A coherent, reproducible negative result still satisfies the engineering and evaluation goals.

Explain predictions using validation permutation importance for model comparison and a small set of actual input values. Correlated inputs may share importance; these explanations are not causal claims. Do not change features after examining test importance.

## 11. Screening scope and the historical-evidence boundary

Day 2 defines the necessary data contract. Day 3 still includes review of the chosen standard and field mapping, as in the existing plan.

Proposed rule profile: `HALALIFY_ASSET_ENTRY_V1`, based on the MSCI Islamic Index Series **asset-denominator entry rules**, May 2025. The three proposed entry limits are debt/assets <= 0.30, (cash + interest-bearing securities)/assets <= 0.30, and (receivables + cash)/assets <= 0.46. Business activity review uses the document's exact scope and definitions, including its prohibited-income test. Do not substitute a generic industry filter or revenue denominator. MSCI also has different retention/exit rules and a market-capitalization variant. [S8]

Our proposed prototype reapplies entry tests at each assessment and does not replicate MSCI index membership, retention buffers, or proprietary business-involvement research. It remains a proposed academic profile until domain-reviewed. Applying this 2025 rule specification to older evidence would be a retrospective fixed-rule simulation, not the official historical compliance verdict. Freeze source edition and configuration hash.

Return `compliant`, `non_compliant`, `needs_review`, or `insufficient_data`, with evidence and per-rule results. Missing prohibited-income data is unknown, not zero. Only an evidence-supported `compliant` result under a reviewed profile enables inclusion; a known failing rule can reject even when another input is absent. These are application states, not claims that MSCI uses the same state labels.

For historical use, retain fiscal dates, filing acceptance date/time, source document and version. A company report ending December 31 but published February 15 is unavailable in January. Later restatements must not overwrite the earlier information set. Carry a report forward only after its availability date, with a documented freshness limit. [S6]

Two deliverable tracks keep the four-week project feasible:

- **Forecasting track:** the 50-stock price-based experiment can proceed independently of unavailable historical screening data. Report it as general market-model evaluation.
- **Screening/portfolio track:** demonstrate current, documented screening and portfolio eligibility. Run a historical compliant portfolio evaluation only for periods and stocks with reconstructable dated business and financial evidence. If that evidence is unavailable, deliver the current screening demo plus the general market-model evaluation; do not relabel today's survivors as historically compliant.

Review company activities from filings and segment notes, not just names. Automatic extraction may need manual interpretation. Record who reviewed ambiguous classifications. Screening correctness should be tested with independently checked example decisions and ratio boundary tests; it is not an ML accuracy contest. Any future reference labels must use the same standard and date.

## 12. Portfolio experiment specified for later implementation

The main purpose is to test whether classifications improve allocation relative to the same eligible pool. It is not live brokerage execution.

At each 20-session signal anchor, retain only evidence-supported eligible stocks with fresh inputs. Define a ranking score `p_return_high - p_return_low`; it is a ranking score, not expected percentage return. For the moderate profile, additionally require `p_risk_high <= 0.50`. Rank descending, with ticker ascending as the deterministic tie-breaker, and select at most ten stocks.

Start with equal weights among selected stocks, cap each at 15%, and cap each broad study group at 30% by proportionately scaling down weights in an over-limit group. Leave any remainder in uninvested cash with zero assumed return. Do not renormalize in a way that breaches the caps. If fewer than eight eligible selections remain, return an insufficient-diversification status and hold cash in the simulation. These are fixed prototype constraints, not personalized suitability rules.

If the selected return model is the deterministic historical baseline, rank by `ret_20d` instead of inventing probabilities. If the selected risk model is the historical baseline, the moderate profile permits low/medium risk classes, the conservative profile permits low only, and the aggressive profile adds no risk-class filter. Register these baseline variants explicitly; they do not supply calibrated confidence scores.

For a later three-profile demo, a conservative version uses `p_risk_high <= 0.20`; an aggressive version removes this additional classifier filter. The same screening, holding and group caps apply. The thresholds are application design settings and must not be described as calibrated loss probabilities.

Use signals after close at `t`; trade at the next session close `t+1`. The next planned signal is at `t+20` and its trade at `t+21`. Update net asset value daily with drifted holdings. If a held stock loses eligibility on new evidence, schedule exit for the next available session close. Missing or suspended prices require explicit valuation/execution treatment, never zero-return imputation or retrospective disappearance from the portfolio.

Transaction assumptions:

- Start at normalized wealth 1; fractional shares allowed for the simulation; no leverage or short sales.
- Charge 10 basis points per dollar bought or sold, with 0 and 25 basis point sensitivity reports. These are assumptions, not observed broker fees.
- `traded_fraction = sum(abs(new_stock_weight - drifted_pretrade_stock_weight))`.
- Cost fraction = `0.001 * traded_fraction` in the main case. Report half this traded fraction as conventional one-way turnover so the definition is unambiguous.
- Include the first purchase and final liquidation costs. Accrue no interest on cash. Taxes and actual broker execution are outside this prototype.
- If outcomes rely on provider adjusted total returns, do not separately add dividends. Report them as gross of purification unless a separately verified dividend ledger applies the approved purification method.

Compare with equal weight across all same-date eligible stocks under the same caps, cash rule, execution lag, and costs, without the ML ranking/risk filter. Also report SPY buy-and-hold as broad market context, not a compliant recommendation. If strict historical screening cannot be reconstructed, the first comparison must be explicitly described as an unscreened research comparison or omitted.

Report cumulative return, CAGR, annualized daily volatility, maximum drawdown, mean holdings, turnover, exposure/cash and cost impact. If reporting a zero-cash-rate Sharpe, label the zero-rate assumption. A Treasury-yield-based Sharpe is an optional statistical benchmark with documented annual-yield conversion and availability; it does not mean the portfolio invests in Treasury bills. Do not add overlapping 20-day target returns together as if they were executable portfolio profits.

## 13. Backend handoff and ownership

HalalifyAPI remains responsible for authentication, persistence, schedules and user-facing API access. HalalifyAI owns features, labels, screening calculations, models and the experimental evaluation. Temporary collection scripts may live in HalalifyAI while both developers use the same normalized schema. Avoid implementing two inconsistent normalization pipelines.

| Work | Owner | Review or handoff |
| --- | --- | --- |
| Universe, price data, feature formulas | AI developer A | AI developer B checks calculations and sources. |
| Labels, temporal splits, screening evidence | AI developer B | AI developer A checks leakage; domain reviewer checks screening. |
| Return model | A | B reproduces the experiment. |
| Risk model | B | A reproduces the experiment. |
| Schema, storage and endpoint integration | Backend developer | Both AI developers review the dictionary. |

The companion dictionary specifies logical tables and a prediction response. No actual backend repository or database has been inspected in this task. Names are a proposed contract that can be mapped onto existing tables without unnecessary rewrites.

### Ready-to-use backend discussion checklist

| Question to resolve | Proposed answer | Meeting status |
| --- | --- | --- |
| How is a company identified permanently? | `instrument_id` plus CIK and ticker history; ticker is not the permanent key. | Not yet confirmed |
| Who downloads and normalizes data? | One agreed adapter; backend schedules/persists, AI validates calculations. | Not yet confirmed |
| Can historical prices/actions be retained by dataset version? | Preserve source snapshot and unique instrument/session keys. | Not yet confirmed |
| Is a separate adjusted close available? | Required; capture adjustment policy and volume basis. | Not yet confirmed |
| Can filings be stored by accession and availability timestamp? | Required for historical financial features and screening. | Not yet confirmed |
| Are restricted/interest-income components actually available? | Return null and insufficient evidence when absent. | Not yet confirmed |
| Where are targets stored? | Training/evaluation storage, never live input payloads. | Not yet confirmed |
| What does the frontend receive? | Class probabilities, thresholds, horizon, versions, timestamps, screening reasons. | Not yet confirmed |
| Can the system abstain? | Return insufficient/stale data status, not made-up prices or predictions. | Not yet confirmed |
| Who reviews the screening rule profile? | Named supervisor/domain reviewer in the rule version record. | Not yet confirmed |

The team must have this discussion; no message has been sent and no meeting has been represented as completed.

## 14. Day 2 learning walkthrough

Read this section together before implementing downloads.

1. **State the question in one sentence.** Explain what will be known today and what will only be known 20 sessions later. Write that sentence in your own words. You are designing a measurable experiment, not selecting a guaranteed profitable stock.
2. **Read the 50-stock list.** Each ticker identifies a company to collect. Explain why a research candidate is not automatically compliant and why conventional banks are useful rejection cases. Confirm that future performance is not a selection criterion.
3. **Draw the periods on paper.** Mark early-2016 warm-up, usable 2016–2020 training, 2021–2022 validation and 2023–2025 test. Training teaches; validation selects; test measures the frozen choices. Do not move the dates after seeing results.
4. **Separate the clocks.** Daily data means one record per exchange session. A 60-day lookback summarizes the past. A 20-day horizon defines the future answer. A Pakistan calendar date is not the exchange's trading-date definition.
5. **Work one example.** If an adjusted series rises from 100 at `t` to 108 at `t+20`, the label is 0.08. At `t`, 108 is unknown. A previous 20-session return may be an input; the next 20-session return must be excluded from inputs.
6. **Read one dictionary row fully.** For `vol_20d`, explain source, 20 daily returns, sample standard deviation, annualization, unit and warm-up. Repeat for `filing_available_at`: it controls when financial evidence can enter an experiment.
7. **Explain the two outputs.** Return asks about growth; volatility asks about variability. The same stock can have a high expected return class and a high predicted volatility class. Quantile cutoffs are computed later from training outcomes, not guessed today.
8. **Walk through the boundary gap.** A late-December training example may need January prices for its label. It must be removed from that training partition if January belongs to validation. Twenty missing training dates across all stocks is different from twenty missing table rows.
9. **Meet the backend developer using section 13.** Record actual support, gaps and owners in the checklist. Ask for sample records for a price row, a filing and a prediction. Do not ask the backend developer to invent unavailable prohibited-income values.
10. **Commit these documents after team review.** Suggested repository paths: `HalalifyAI/docs/experiment_design.md` and `HalalifyAI/docs/data_dictionary.md`. Use your established feature-branch/review workflow; no repository or branch was changed by this deliverable.

Day 2 is complete when the two AI developers can explain these choices, the contract is reviewed with the backend developer, and unresolved provider/screening issues have named owners. Downloading the full dataset, calculating thresholds and training models belong to subsequent tasks.

## 15. Reproducibility and acceptance checklist

- [ ] Universe manifest has the 50 proposed tickers, exclusions if any, identity checks and version.
- [ ] Raw source snapshot, retrieval timestamp, parameters, adjustment basis and file hashes are retained.
- [ ] Session calendar and environment/package versions are pinned; credentials are not committed.
- [ ] Feature code produces the dictionary's 16 fields in the declared order and identical units.
- [ ] Labels use exactly 20 future exchange sessions; no target is a feature.
- [ ] Split assertions pass: `max(training.label_end_date) < min(evaluation.as_of_date)` for every boundary.
- [ ] Training-only class cutoffs and preprocessing parameters are serialized with the model.
- [ ] Core model comparisons use identical rows and show baseline results and coverage.
- [ ] Test decisions are frozen before inspecting performance; revisions are logged honestly.
- [ ] Screening evidence is dated, missing values are preserved, and profile review is recorded.
- [ ] Portfolio tests obey the execution lag, cash and cost rules, and evidence gate.

Store each run's Git commit, data version, universe version, calendar version, feature version, label version, model settings, seed, split dates, excluded counts, runtime and metric outputs. Save large data/models outside Git; commit scripts, documentation and small permitted examples.

## 16. Sources and evidence boundaries

Sources checked on 2026-09-25. These links support factual descriptions; the chosen 50-stock cohort, feature windows, dates, grid and portfolio limits are our experimental decisions.

- **S1.** Kumbure et al. (2022), *Machine learning techniques and data for stock market forecasting: A literature review*. User-supplied `Research.pdf`, especially sections 2 and 5.3 and the study limitations. [DOI](https://doi.org/10.1016/j.eswa.2022.116659). A review of heterogeneous studies, not a controlled comparison proving the best model for Halalify.
- **S2.** Boogie Software (2019), [Predicting Stock Returns with a Neural Network](https://boogiesoftware.com/blog/predicting-stock-returns-with-a-neural-network-2-2/), also supplied as Markdown. Illustrates monthly return prediction and portfolio ranking; acknowledges survivorship bias. Its historical performance does not transfer to our universe.
- **S3.** Gu, Kelly and Xiu, [Empirical Asset Pricing via Machine Learning](https://doi.org/10.1093/rfs/hhaa009). Primary research supporting comparison of linear/nonlinear methods; a different dataset and task specification.
- **S4.** yfinance maintainer [download API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html) and [repository/use notice](https://github.com/ranaroussi/yfinance). Parameters and research-access limitations; not exchange certification.
- **S5.** Alpha Vantage [official documentation](https://www.alphavantage.co/documentation/#dailyadj), daily adjusted endpoint. Alternative is premium, not a free-access promise.
- **S6.** SEC [EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). Official submissions and XBRL access; taxonomy/context and original disclosures still require interpretation.
- **S7.** Federal Reserve Bank of St. Louis [VIXCLS](https://fred.stlouisfed.org/series/VIXCLS), [DGS3MO](https://fred.stlouisfed.org/series/DGS3MO), and [real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html). Observation date and when an observation was known are different.
- **S8.** MSCI [Islamic Index Series Methodology, May 2025](https://www.msci.com/documents/10199/8a59e89f-5134-de21-6a03-082ecfaa9e42), sections 2.1–2.2.1. Reference for a proposed academic entry-rule profile; does not grant certification or reproduce proprietary screening evidence.
- **S9.** NYSE [holidays and trading hours](https://www.nyse.com/trade/hours-calendars). Calendar reference; pin historical sessions in implementation.
- **S10.** State Street [SPY fund objective](https://www.ssga.com/nl/nl/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy). Broad market benchmark, not a Shariah-screened investment selection.
- **S11.** scikit-learn [TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html). Its gap is measured in samples; our date-grouped adaptation is specified above.
- **S12.** scikit-learn [common pitfalls and leakage](https://scikit-learn.org/stable/common_pitfalls.html). Training-only preprocessing and pipeline guidance.
- **S13.** scikit-learn [HistGradientBoostingClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html). Early-stopping and validation-fraction behavior. Pin the installed version rather than relying on future defaults.

## 17. Revision record

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-09-25 | Initial complete Day 2 specification; preserves the classifier-first plan, removes duplicate momentum fields, adds date-based purging, and defines historical-screening evidence limits. |
