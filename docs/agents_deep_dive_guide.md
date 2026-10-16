# HalalifyAI Architecture & Engineering Masterclass
*A comprehensive guide to Sections 7 through 38 of AGENTS.md*

---

## Welcome to the Masterclass!

Hello and welcome! In the first part of your journey through [AGENTS.md](file:///d:/BSSE-Final%20Year/7th%20Semester/FYP/HalalifyAI/AGENTS.md), you learned about:
- Why **Alpaca SIP** (consolidated tape across all US exchanges) replaces single-exchange feeds like IEX.
- Why **SPY** is included (not as a portfolio constituent, but as an external market benchmark/anchor).
- Why we distinguish between **split-adjusted prices** (for dollar volume and technical levels) and **dividend+split adjusted prices** (for actual investor returns).
- The 50-stock research universe and how it started.

Now, we step into the engine room: **how raw SEC fundamentals are handled without look-ahead bias, how the exact 16 mathematical features are constructed, how Machine Learning classification and chronological validation are designed, how rule-based Shariah screening operates independently, and how the entire end-to-end portfolio optimizer and FastAPI service fit together.**

Let's break down each concept step by step, using clear analogies and concrete examples.

---

## Table of Contents
1. [The SEC EDGAR Challenge: Facts, Concepts, and Look-Ahead Bias](#1-the-sec-edgar-challenge)
2. [The 16 Core Market Predictors (Formulas & Intuition)](#2-the-16-core-market-predictors)
3. [The ML Prediction Engine: Targets, Models, and Purging](#3-the-ml-prediction-engine)
4. [Rule-Based Shariah Screening: Orthogonal to ML](#4-rule-based-shariah-screening)
5. [User Risk Preferences & Portfolio Optimization](#5-user-risk-preferences--portfolio-optimization)
6. [Leak-Free Backtesting and Survivorship Bias](#6-leak-free-backtesting-and-survivorship-bias)
7. [System Architecture, Coding Standards, and Current Progress](#7-system-architecture-and-status)
8. [Quick Reference Glossary & The 12 Golden Rules](#8-quick-reference-glossary)

---

## 1. The SEC EDGAR Challenge

### 1.1 Why Fundamental Data is Tricky
In stock prices, a trade happens at 2:00 PM and you immediately know the price. Financial statements (10-Q quarterly reports and 10-K annual reports) are totally different.

When a company files an SEC report, three dates exist:
1. **Period End (`period_end`)**: e.g., `2024-03-31` (The quarter closed on March 31).
2. **Filing Date (`filing_date`)**: e.g., `2024-05-01` (The accountants published the report on May 1).
3. **Available From Session (`available_from_session`)**: e.g., `2024-05-02` (The first day trading actually takes place *after* the public disclosure).

> 🎓 **Teacher's Example: The Report Card Analogy**
> Imagine your school term ends on December 15 (`period_end`). You took your exams, but teachers were grading them. Your final report card was officially mailed on January 5 (`filing_date`).
> Can an employer judge your academic performance on December 20? **No!** The public did not know your grades until January. If our machine learning algorithm uses your December 15 numbers on December 20, it is **cheating by peeking into the future** (Look-Ahead Leakage).
> In HalalifyAI: We conservatively enforce `available_from_session` as the **first trading session AFTER the filing date**.

### 1.2 XBRL Concepts and Quarantining
Public companies submit numbers tagged in **XBRL** (*eXtensible Business Reporting Language*).
- For cash, Apple might use `CashAndCashEquivalentsAtCarryingValue`, while another company might use `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`.
- Some values might be corrupted (negative assets, foreign currencies like EUR/CAD, or period end dated *after* filing date).

**The HalalifyAI Principle:**
- **Never guess or overwrite data with absolute values (`abs()`).**
- Questionable data is routed to a **Quarantine table** (`quarantined_facts.csv`) for human audit.
- Keep source files immutable in `data/raw/`.

---

## 2. The 16 Core Market Predictors

Instead of throwing hundreds of arbitrary indicators into a model, HalalifyAI specifies **exactly 16 ordered, float64 market predictors**. They capture momentum, volatility, trend, liquidity, and broader market correlation.

Let:
- $P_t$ = Validated **adjusted close** (split + dividend adjusted, reflecting total economic return).
- $C_t$ = Non-dividend adjusted, **split-consistent close** (actual quoted price level).
- $V_t$ = Split-adjusted volume.
- $r_t = \frac{P_t}{P_{t-1}} - 1$ = Daily percentage return.
- Annualization factor = $\sqrt{252}$ (252 exchange trading sessions in a year).

### Summary Table of the 16 Predictors

| # | Feature Name | Formula / Definition | Intuition / Why It Matters |
|---|---|---|---|
| **1-4** | `ret_1d`, `ret_5d`, `ret_20d`, `ret_60d` | $\frac{P_t}{P_{t-k}} - 1$ for $k \in \{1, 5, 20, 60\}$ | Short-, medium-, and long-term momentum. How much has the stock grown over 1 day, 1 week, 1 month, and 1 quarter? |
| **5-6** | `vol_20d`, `vol_60d` | Sample standard deviation of trailing daily returns $\times \sqrt{252}$ (with sample $ddof=1$) | Annualized historical volatility. Measures price turbulence/instability over 1 month and 1 quarter. |
| **7** | `downside_dev_20d` | $\sqrt{\frac{1}{20}\sum_{i=1}^{20} \min(r_i, 0)^2} \times \sqrt{252}$ | Downside risk (Semi-deviation). Normal volatility penalizes upward jumps; downside deviation **only penalizes drops**! |
| **8** | `max_drawdown_60d` | Maximum peak-to-trough fractional drop over 61 adjusted closes: $\max_{\tau \le t} \left( \frac{\max_{s \le \tau} P_s - P_\tau}{\max_{s \le \tau} P_s} \right)$ | Worst-case crash experienced by an investor who bought at the peak in the last 60 sessions. |
| **9-10**| `price_sma20_ratio`, `price_sma50_ratio` | $\frac{P_t}{\text{SMA}_k(P)} - 1$ for $k \in \{20, 50\}$ | Distance from moving average. Positive means trading above trend (bullish/stretched); negative means trading below trend. |
| **11**| `rsi_14` | Wilder's 14-period Relative Strength Index (recursive smoothing with $\frac{13}{14}$ weight) | Overbought/Oversold oscillator bounded $[0, 100]$. Edge cases: no losses $\to 100$, no gains $\to 0$, both zero $\to 50$. |
| **12**| `volume_ratio_20d` | $\frac{V_t}{\text{SMA}_{20}(V)}$ | Volume surge detector. Is trading activity today unusually high compared to its 20-day average? |
| **13**| `log_dollar_volume_20d`| $\ln\left(1 + \frac{\text{mean}_{20}(C \times V)}{1\text{ USD}}\right)$ | Liquidity indicator. Large institutional portfolios need high dollar volume to enter/exit positions without moving the price. |
| **14**| `beta_60d` | $\frac{\text{Covariance}(r_{\text{stock}}, r_{\text{SPY}})}{\text{Variance}(r_{\text{SPY}})}$ over 60 trading days | Sensitivity to the overall US market. $\beta = 1.5$ means if SPY rises 1%, the stock tends to rise 1.5%. |
| **15**| `market_ret_20d` | $\frac{P_{\text{SPY}, t}}{P_{\text{SPY}, t-20}} - 1$ | 20-day return of the SPY index. Tells the model what the overall market climate was. |
| **16**| `market_vol_20d` | Trailing 20-return sample standard deviation of SPY $\times \sqrt{252}$ | Macro market volatility. Is the broad market calm or in a state of panic? |

> ⚠️ **Strict Computation Requirement:**
> To calculate 60 daily returns, you need **61 consecutive trading sessions**. If there is a missing session, you cannot forward-fill or guess; that window is marked invalid.

---

## 3. The ML Prediction Engine

### 3.1 Targets: Two Separate Classification Problems
Instead of trying to predict exact stock prices (which is notoriously noisy), HalalifyAI formulates two distinct 3-class classification problems over a **20-trading-day forward horizon** (approx. 1 calendar month):

1. **Future Return Target (`future_return_20d`)**:
   $$R_{t \to t+20} = \frac{P_{t+20}}{P_t} - 1$$
   Discretized into **Low**, **Medium**, **High**.
2. **Future Risk Target (`future_vol_20d`)**:
   Realized annualized volatility over the upcoming 20 sessions:
   Discretized into **Low**, **Medium**, **High**.

> 🔑 **Golden Rule of ML Discretization:**
> The quantile thresholds (the 33.3% and 66.7% cutoffs dividing Low/Medium/High) **must be calculated on the Training Set only**! Never use validation or test data to determine what qualifies as "High Return".

### 3.2 Chronological Partitioning & Purging
Standard ML workflows use random cross-validation (`train_test_split(shuffle=True)`). **In financial time-series, random shuffling is fatal.**

```
Historical Timeline:
[------ Training: 2016 - 2020 ------] -> [--- Validation: 2021 - 2022 ---] -> [--- Test: 2023 - 2025 ---]
```

#### What is "Purging" and Why is it Necessary?
Suppose today is **December 20, 2020** (near the end of the training set).
- To compute the 20-day forward return label, the model looks ahead 20 sessions to **January 20, 2021**.
- But January 2021 belongs to the **Validation set**!
- If you include that training row, the model has trained on market outcomes that occurred during the validation period!
- **Purging Rule:** Discard any row in the training set whose label end date ($t+20$) crosses into or overlaps the next partition.

```
       Training Window                     Validation Window
[... Nov 2020 ... Dec 10 ... Dec 31] | [Jan 02, 2021 ... Dec 2022]
                   |___________|
                         \
            Label looks 20 days forward into Jan 2021!
            --> THIS ROW MUST BE PURGED! <--
```

### 3.3 Candidate Models & Evaluation
Deep learning (LSTMs, Transformers) is often prone to overfitting on small market universes. HalalifyAI focuses on robust, interpretable classical baselines:
1. **Logistic Regression** (with `StandardScaler`, $C \in [0.1, 1, 10]$)
2. **Random Forest** (300 trees, depths 6 and 12)
3. **HistGradientBoosting** (lightweight gradient boosting, leaf regularized)

**Metrics:** We evaluate primarily on **Macro F1-score**, Per-class Precision/Recall, and Confusion Matrices (because pure accuracy hides class imbalance).

---

## 4. Rule-Based Shariah Screening

### 4.1 Orthogonality: ML vs. Shariah
A critical architecture decision in HalalifyAI is that **ML Prediction and Shariah Screening are completely separate (orthogonal) systems**:

```
        ┌─────────────────────────┐
        │ 50 Stock Universe       │
        └────────────┬────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐     ┌────────────────────────┐
│ ML Return & Risk│     │ Rule-Based Shariah     │
│ Classification  │     │ Screening Engine       │
│ (High/Med/Low)  │     │ (SEC Fundamentals +    │
└────────┬────────┘     │ Business Activities)   │
         │              └───────────┬────────────┘
         │                          │
         │     Compliant Only       │ (Rejects non-compliant
         │   ┌──────────────────────┘  stocks, e.g. JPM, BAC)
         ▼   ▼
┌─────────────────────────┐
│ Portfolio Optimization  │
│ & Risk Constraints      │
└─────────────────────────┘
```

- The ML models are trained on the broader market universe so they understand general financial mechanics.
- But when it comes to constructing a portfolio for the user, **any stock failing the Shariah screen is strictly excluded**.

### 4.2 Screening Criteria (Example: Proposed Asset Entry Profile)
While the final supervisory standard is pending formal domain approval, the prototype implements an explicit rule-set (inspired by standards such as MSCI Islamic / AAOIFI):
1. **Business Activity Screen:** Prohibits conventional banking/interest, alcohol, gambling, weapons, non-halal food, adult entertainment, etc.
2. **Financial Ratio Thresholds (using Total Assets as denominator):**
   - **Debt Screen:** $\frac{\text{Total Debt}}{\text{Total Assets}} \le 30\%$
   - **Cash & Interest-bearing Securities Screen:** $\frac{\text{Cash} + \text{Interest Bearing Securities}}{\text{Total Assets}} \le 30\%$
   - **Receivables Screen:** $\frac{\text{Accounts Receivable} + \text{Cash}}{\text{Total Assets}} \le 46\%$
3. **Evidence Freshness:** Financial statements cannot be older than 180 days; business disclosures cannot be older than 450 days. If data is missing or stale, status is `needs_review` or `insufficient_data`—**never assume missing debt is zero!**

---

## 5. User Risk Preferences & Portfolio Optimization

### 5.1 Architecture Decision on Risk Preference
In the past, an SRS requirement suggested: *"If a user is conservative, change the ML cutoff so that a stock needs higher returns to be called 'High Return'"*.

**Why this was rejected by sound engineering:**
Changing the definition of "High Return" based on user mood means the ML model has no consistent, objective meaning!

**The Correct Solution:**
Keep the ML model classes objective and stable. Apply the user's risk preference inside the **Portfolio Optimizer**:
- **Conservative User:** Cap exposure to high-risk stocks (e.g., maximum probability of high risk $\le 0.20$), allocate more weight to defensive, low-volatility compliant stocks, or hold uninvested cash.
- **Moderate User:** Balanced constraints (e.g., high-risk probability cap $\le 0.50$).
- **Aggressive User:** Focus heavily on maximizing high-return probability with looser risk caps.

### 5.2 Portfolio Optimization Constraints
- **Long-Only:** Weights $w_i \ge 0$, no short selling, no margin/borrowing leverage (consistent with Islamic finance principles).
- **Fully Allocated or Cash:** $\sum w_i \le 1.0$ (uninvested portions held in cash yielding 0%).
- **Position Cap:** Maximum 15% in any single company (ensures diversification).
- **Sector/Group Cap:** Maximum 30% in any single industry group.
- **Minimum Breadth:** Must select at least 8 compliant stocks; otherwise hold cash.
- **Realistic Friction:** Model 10 basis points (0.10%) of trading fee per rebalance.

---

## 6. Leak-Free Backtesting and Survivorship Bias

### 6.1 Point-in-Time Backtesting Routine
Every 20 exchange sessions (monthly), the backtester simulates an investor sitting at their computer on date $T$:
1. Query only prices and SEC filings available on or before date $T$ (`available_from_session` $\le T$).
2. Compute the 16 features as of date $T$.
3. Run the frozen ML models to get predicted Return and Risk classes.
4. Run the Shariah screen using the most recent valid financial reports available by date $T$.
5. Pass compliant stocks and predictions to the portfolio optimizer.
6. Execute portfolio rebalance at session $T+1$'s closing price.
7. Track performance over the next 20 sessions until the next rebalance date.

### 6.2 Understanding Survivorship Bias
> 🎓 **Teacher's Example: The High School Reunion**
> If you visit your 30th high school reunion and see that every single attendee has a net worth over $1 million, you might conclude: *"Everyone from my high school became rich!"*
> But what about the classmates who struggled, moved away, or passed away? They simply didn't attend the reunion!
> 
> Similarly, our research universe consists of 50 companies that are large and famous **today** (like Apple, Nvidia, Microsoft). Testing our strategy on companies that survived and prospered introduces **survivorship bias**.
> **HalalifyAI Rule:** We openly document this limitation in our thesis and reports, rather than pretending our backtest represents an unbiased simulation of the entire US market over the last 10 years.

---

## 7. System Architecture and Status

### 7.1 Separation of Services
```
[ Frontend: Next.js / TypeScript ]
               │
               ▼ REST (Auth, User Profile, Onboarding)
[ Backend: Node.js / Express (HalalifyAPI) ]
               │
               ▼ Internal HTTP / JSON
[ AI Engine: Python / FastAPI (HalalifyAI) ]
   ├── /health
   ├── /screen (Run Shariah verification)
   ├── /predict (Generate 20-session Return & Risk)
   ├── /optimize (Construct risk-adjusted compliant portfolio)
   └── /backtest (Run historical leak-free simulation)
```

### 7.2 Directory Blueprint
```
HalalifyAI/
├── configs/          # universe.json, screening rules, experiment specs
├── data/
│   ├── raw/          # Immutable provider downloads (Alpaca, SEC CIK JSONs) [Git ignored]
│   ├── interim/      # Reconciled daily prices, extracted SEC candidate facts [Git ignored]
│   ├── processed/    # 16-feature matrix, future 20d labels [Git ignored]
│   └── samples/      # Small fixtures committed for unit tests
├── docs/             # experiment_design.md, data_dictionary.md, etc.
├── reports/
│   └── validation/   # Data audits, coverage checks, pilot test logs
├── src/
│   ├── api/          # FastAPI server and route handlers
│   ├── data/         # Ingestion, calendar audits, SEC extraction
│   ├── features/     # Exact 16 market feature calculations
│   ├── labels/       # 20-day forward return/volatility targets & split manifests
│   ├── models/       # Training, inference, and baseline models
│   ├── screening/    # Rule-based Shariah screening logic
│   └── optimization/ # Portfolio optimization and rebalancing simulation
└── tests/            # Pytest suite
```

### 7.3 Work Done vs. Pending (Handoff Truth)
To maintain academic honesty, never invent completed milestones:
- ✅ **Done:** Reconciled SIP price series, corporate action pilot (AAPL split/dividend), CIK mappings, SEC expanded candidate extraction, 15 unit tests passed.
- ⏳ **Current Focus:** Generating the validated 16-feature matrix and 20-day forward purged labels.
- 📌 **Pending:** Formal Shariah scholar/domain sign-off on exact thresholds, model training & hyperparameter search, portfolio optimizer backtests, FastAPI integration endpoints.

---

## 8. Quick Reference Glossary & The 12 Golden Rules

### Glossary of Key Terms
- **Session:** An exchange trading day (excluding weekends and US market holidays).
- **SPY:** An exchange-traded fund tracking the S&P 500 index. Used purely as a market baseline for beta and market returns, not as a portfolio stock.
- **CIK:** Central Index Key, the unique 10-digit number assigned to each company by the SEC.
- **Look-Ahead Leakage:** An error where future information is inadvertently exposed to an ML model during feature creation or evaluation.
- **Purging:** Removing training instances whose target measurement window overlaps with the start of a subsequent validation/test window.
- **Wilder's Smoothing:** An exponential moving average technique with smoothing factor $\alpha = \frac{1}{N}$ used in RSI.
- **Downside Deviation:** A risk measure that only squares negative returns below a target (or zero), ignoring positive upside variance.

---

### The 12 Golden Rules of HalalifyAI

1. **Target Market:** Initial focus is strictly on U.S. equities.
2. **Separation of Concerns:** ML prediction and Shariah screening are two independent components.
3. **Compliance Guarantee:** Final recommended portfolios must contain **only** stocks that pass Shariah screening.
4. **No Look-Ahead Leakage:** Never use data before it was publicly known in historical time.
5. **SEC Filing Timestamps:** Company fundamentals are only usable from the first trading session *after* their filing date.
6. **Chronological Splitting:** Always split Train $\to$ Validation $\to$ Test chronologically with purging. Never shuffle.
7. **Threshold Integrity:** Target quantile cutoffs (Low, Medium, High) must be fitted on training data alone.
8. **Data Verification:** Use verified SIP feeds and distinguish split-adjusted volume from dividend-adjusted prices.
9. **Academic Honesty:** Do not fabricate Shariah rules, backtest results, or F1 metrics.
10. **Risk Preference Handling:** User risk appetite modifies portfolio weights and constraints, never ML class definitions.
11. **Gating & Validation:** Validate input features, missing values, and calendar gaps before training models.
12. **Data & Secret Hygiene:** Keep raw provider data immutable and never commit `.env` or API credentials to Git.

---

*This study document was prepared directly from [AGENTS.md](file:///d:/BSSE-Final%20Year/7th%20Semester/FYP/HalalifyAI/AGENTS.md) as a complete companion guide for HalalifyAI research and development.*
