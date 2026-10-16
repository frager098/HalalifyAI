# HalalifyAI — Comprehensive Guide to Data Sources, Feeds, and Price Adjustments

**Document Type:** Educational & Technical Training Guide  
**Project:** HalalifyAI (AI-Powered Shariah-Compliant Smart Portfolio Management System)  
**Target Audience:** FYP Teammates, Machine Learning Engineers, and Reviewers  

---

# Welcome & Objectives

Welcome to the comprehensive data guide for **HalalifyAI**. 

In quantitative finance and machine learning, **data quality is your ceiling**. If mathematical nuances like dividend adjustments, exchange feeds, point-in-time filing dates, or corporate mergers are misunderstood, models will learn artificial patterns and fail completely in real-world conditions.

By the end of this document, every team member will clearly understand:
1. What **Feeds** (SIP vs. IEX) actually mean in market infrastructure.
2. What an **Index Fund / ETF (SPY)** is and why it serves as our benchmark rather than an investment asset.
3. Why specific universe assets like **LIN (Linde plc)** have unique timeline rules.
4. Why our project had **different data snapshots** and why we do not mix them.
5. The deep mathematical and practical differences between **`adjustment="split"`** and **`adjustment="all"`**.
6. The critical rules for extracting **SEC EDGAR Fundamentals** without look-ahead bias.

---

# 1. Understanding US Stock Market Feeds (IEX vs. SIP)

To understand our data, we must first understand how US stock exchanges work.

Unlike some countries where all stocks trade on a single centralized building, US equities trade across **multiple competing exchanges simultaneously** (e.g., NYSE, NASDAQ, Cboe, IEX, and alternative trading systems).

```
   [ NYSE ]      [ NASDAQ ]      [ IEX ]      [ Cboe ]
      \              |              /           /
       \             |             /           /
        ▼            ▼            ▼           ▼
   =================================================
       SIP (Securities Information Processor)
        Consolidates ALL trades into 1 stream
   =================================================
                     │
                     ▼
          [ Alpaca SIP Data Feed ]
                     │
                     ▼
             [ HalalifyAI Pipeline ]
```

### What is IEX?
* **IEX (Investors Exchange LLC)** is **one single exchange** among many.
* **Why it matters**: If you request market data from IEX only, you only see trades executed on that specific floor. This results in fragmented liquidity, lower volume numbers, and in our case, historical records that only began around mid-2020.
* **Project Status**: **Retired / Superseded**. We do not use IEX-only data for our core 10-year research.

### What is SIP?
* **SIP (Securities Information Processor)** is the **US government-mandated centralized consolidation engine**.
* It continuously aggregates real-time quotes and executed trades from **every single registered exchange** in the United States.
* **Why it matters**: Sourcing SIP data ensures we get the true national best bid and offer (NBBO), complete nationwide trading volume, and continuous history back to 2016.
* **Project Status**: **Active standard**. HalalifyAI uses Alpaca's SIP feed.

---

# 2. Key Symbols & The Concept of a "Benchmark"

### What is an Index Fund / ETF?
An **Index Fund** is an investment vehicle designed to track a specific basket of assets. 
* The **S&P 500** is an index of the 500 largest publicly traded American corporations.
* **SPY (SPDR S&P 500 ETF Trust)** is an Exchange-Traded Fund structured as a Unit Investment Trust that physically holds shares of all 500 companies in proportion to their market weight.
* SPY is **not an operating company**; it produces no goods and has no manufacturing plants. It is simply a container holding 500 stocks.

### Why is SPY in our dataset if it cannot be in our Shariah portfolio?

```
                       [ 500 S&P Companies ]
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     ▼                                                       ▼
[ Compliant Stocks ]                                [ Non-Compliant Stocks ]
(e.g., Tech, Healthcare)                           (e.g., Banks, Alcohol, Casinos)
     │                                                       │
     └───────────────────────────┬───────────────────────────┘
                                 │
                     All packaged inside SPY!
                                 │
                                 ▼
             ❌ SPY fails Shariah Screening as a whole
                                 │
                                 ▼
             ✅ BUT SPY is our Market Benchmark (Yardstick)
```

1. **Why SPY is NOT an investment asset for us:**
   Because SPY automatically includes conventional interest-bearing commercial banks (JPMorgan, Bank of America), alcohol producers, casinos, and high-debt firms, the fund as a unit is non-compliant.
2. **Why SPY is mandatory for Machine Learning:**
   In finance, you cannot evaluate a single stock in isolation. If a stock drops 3% on a day the entire market crashed 5%, the stock was actually resilient. We use SPY to compute:
   * **$\text{Beta } (\beta)$**: How sensitive a stock's returns are relative to broad market swings:
     $$\beta = \frac{\text{Covariance}(R_{\text{stock}}, R_{\text{SPY}})}{\text{Variance}(R_{\text{SPY}})}$$
   * **Market Volatility (`market_vol_20d`)**: The macro volatility environment.

### The Case of LIN (Linde plc)
* **What it is**: Linde plc is a major global industrial gas supplier in our 50-stock research universe.
* **Why it is unique**: Current Linde plc was formed from a cross-border merger between Praxair (US) and Linde AG (Germany). Its current US listing commenced on **2018-10-31**.
* **Strict Research Rule**: 
  * Linde has 1,801 trading sessions in the 2016–2025 study, whereas other stocks have 2,514.
  * **Never invent synthetic price rows** or fabricate history prior to 2018-10-31. Real financial models must respect real listing dates.

---

# 3. Why are there Historical Snapshots in our Documentation?

In [`AGENTS.md`](file:///d:/BSSE-Final%20Year/7th%20Semester/FYP/HalalifyAI/AGENTS.md), you see a table describing four snapshots. 

**Are we using all 4 snapshots simultaneously? NO.**

Think of snapshots as the **version history of our data engineering process**:

```
[Snapshot 1: IEX Data]  ──(Too short: 2020-2026 only)──► RETIRED / DEPRECATED
         │
[Snapshot 2: SIP CSV]   ──(Had 2016-2026, but only 1 price type)──► SUPERSEDED
         │
[Snapshot 3: SPY CSV]   ──(Downloaded SPY independently)──────────► MERGED
         │
         ▼
[Snapshot 4: Reconciled Collection] ──► ✅ CURRENT GROUND TRUTH
 - 50 Universe Stocks + SPY
 - Clean 2016-2025 Window
 - Split vs. All price bases separated
```

### Why document retired snapshots?
In rigorous scientific research and software engineering:
* **Traceability**: If an older experiment recorded 77,455 rows and a newer one recorded 127,501 rows, documenting the snapshots explains *why* without causing confusion.
* **Integrity**: It prevents any engineer or AI agent from accidentally loading an outdated CSV file from a backup folder.

---

# 4. Masterclass: Price Adjustments (`split` vs. `all`)

This is one of the most critical concepts in quantitative investing.

When you download historical daily prices, a company's raw stock price undergoes two major corporate events over time: **Stock Splits** and **Cash Dividends**.

---

### Scenario A: Stock Splits (Adjusted in BOTH modes)
* **What happens**: Apple does a 4-for-1 stock split.
* If the stock was \$400 on Monday, on Tuesday the price becomes \$100, and every shareholder now has 4 shares instead of 1.
* **Why adjustment is needed**: If you didn't adjust, your ML model would think Apple crashed $-75\%$ overnight!
* Both `adjustment="split"` and `adjustment="all"` properly scale historical prices backwards so splits do not create fake price drops.

---

### Scenario B: Cash Dividends (The Key Difference)
* **What happens**: A stock is trading at **\$100**. On the ex-dividend date, the company pays a **\$5 cash dividend** directly into every shareholder's bank account.
* On that morning, the stock price naturally opens at **\$95** because \$5 of cash left the company's balance sheet.
* **The dilemma**:
  * Did the shareholder lose \$5? **No.** They have a \$95 share + \$5 cash = \$100 total wealth.
  * Did the market quote on that day drop to \$95? **Yes.**

---

### Comparison Matrix

| Property | `adjustment="split"` (Close) | `adjustment="all"` (Adjusted Close) |
| :--- | :--- | :--- |
| **Split-Adjusted?** | Yes | Yes |
| **Dividend-Adjusted?** | **No** (Shows actual historical quoted price) | **Yes** (Prices adjusted down to reflect Total Return) |
| **What Volume matches?** | Matches split-adjusted volume | Does not match cash adjustments |
| **What we calculate with it** | **Dollar Volume & Liquidity**<br>`Dollar Volume = Close × Volume` | **Returns, Momentum & Volatility**<br>`ret_1d`, `vol_20d`, `rsi_14`, `drawdowns` |
| **Why?** | Multiplying dividend-adjusted price by volume yields fictional currency volume. | Calculating returns on unadjusted prices treats dividends as artificial market crashes. |

```
                 ┌──────────────────────────────────────────────┐
                 │         Incoming Alpaca SIP Data             │
                 └──────────────────────┬───────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
        [ adjustment = "split" ]                [ adjustment = "all" ]
                    │                                       │
            Raw/Nominal Close                           Adjusted Close
                    │                                       │
                    ▼                                       ▼
          Used for Liquidity:                     Used for Performance:
          - Dollar Volume (C * V)                 - ret_1d, ret_5d, ret_20d
          - Volume Ratios                         - vol_20d, vol_60d, RSI, Beta
```

> ⚠️ **Absolute Rule**: Never copy the `close` column into `adjusted_close` or vice versa. They serve two completely different mathematical purposes.

---

# 5. SEC EDGAR Fundamentals & Point-in-Time Rules

Fundamental indicators (Balance Sheet and Income Statement) come from official SEC filings via the **SEC EDGAR API**.

```
[ SEC EDGAR API ] ──► Raw JSON (Company Facts) ──► extract_sec_fundamentals.py ──► Point-in-Time Dataset
```

### 1. Concepts Extracted
We extract five standardized US-GAAP categories:
1. **`total_assets`** (`Assets`)
2. **`total_debt`** (`LongTermDebtCurrent`, `LongTermDebtNoncurrent`, etc.)
3. **`cash`** (`CashAndCashEquivalentsAtCarryingValue`, etc.)
4. **`revenue`** (`RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`)
5. **`accounts_receivable`** (`AccountsReceivableNetCurrent`)

### 2. The Golden Rule: Preventing "Look-Ahead Bias"
* When a company's fiscal quarter ends on **March 31**, they do not publish results on March 31.
* They might file their **10-Q** report with the SEC on **May 10**.
* **Rule**:
  * `period_end` = 2024-03-31 (the accounting period).
  * `filing_date` = 2024-05-10 (when the public actually saw the report).
  * **Our rule**: The financial data is strictly **unavailable** for ML models or Shariah screening on 2024-04-15. It only becomes available on the **first trading session AFTER `filing_date`**.

---

# 6. Summary Checklist for Team Execution

- [x] **Feeds**: Always use **SIP** for complete US market price coverage.
- [x] **Benchmark**: Use **SPY** for Beta and Market Volatility calculations; do not include SPY in Shariah screening.
- [x] **Instrument Timelines**: Respect genuine listing dates (e.g. **LIN** starts on 2018-10-31; do not fabricate predecessor prices).
- [x] **Liquidity Features**: Calculate `Dollar Volume` using non-dividend-adjusted `split` close.
- [x] **Return/Risk Features**: Calculate `returns`, `volatility`, `RSI`, and `drawdowns` using dividend-adjusted `all` close.
- [x] **Fundamentals**: Join SEC facts on `available_from_session > filing_date` to prevent data leakage.
