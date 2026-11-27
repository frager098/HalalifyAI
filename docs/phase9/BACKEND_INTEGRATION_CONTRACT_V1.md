# Phase 9 backend integration contract, proposed v1

Status: **prepared for review; HTTP route and backend client are not implemented**.
This contract reflects the AI artifacts reviewed through 9.7 and the current
`HalalifyAPI` checkout on branch `main`. The backend has an unrelated local
modification to `src/config/env.js`; this review did not edit that repository
or read its `.env` file.

## Service boundary

`Frontend → HalalifyAPI (Node/Express) → HalalifyAI (Python/FastAPI)`.
HalalifyAPI owns authentication, provider retrieval, ticker/stock-ID mapping,
request orchestration, and its existing `ApiResponse` envelope. HalalifyAI
owns historical feature reconstruction and the two fitted model predictions.
The FastAPI route should be internal to the backend, with no direct public
frontend dependency. The final route name and service authentication policy
must be agreed when 9.8 is implemented; the working path below is a proposal.

## Proposed internal request

`POST /internal/v1/market-predictions`, JSON body:

```json
{
  "contract_version": "phase9-market-prediction-v1",
  "session_date": "2024-05-30",
  "expected_tickers": ["AAPL", "MSFT"],
  "bars": [
    {"ticker": "AAPL", "session_date": "2024-03-01", "adjusted_close": 0.0, "volume": 0, "spy_return": 0.0}
  ],
  "input_provenance": {
    "price_basis": "all_adjusted_close",
    "source_version": "versioned-source-identifier",
    "roster_version": "dated-roster-identifier",
    "availability": "after_close_verified"
  }
}
```

The JSON is a **shape illustration only**: the placeholder price and two-name
roster are invalid and must not be sent as a real prediction request. A valid
request supplies one row for each expected stock and exchange session across
at least 61 consecutive XNYS sessions ending at `session_date`, with 45–50
active peers on the decision date. `expected_tickers` is the verified
**point-in-time** roster for that date, not today's active-stock list. All
rows are ordered by session, then ticker. Prices are positive finite
all-adjusted closes, volumes are finite and nonnegative, and each same-date
SPY return agrees across rows. The first session of a historical series may
have a null SPY return if no earlier SPY close exists; later missing returns
are rejected. Bars must be known after the decision session closes. The
backend must not claim an availability timestamp it does not possess.

The AI route should validate `input_provenance`, but the current Python
`predict_phase9` function accepts only the bars, date, and roster. The route
must reject unsupported/missing provenance before calling it. No user ID,
risk preference, screening mode, SEC field, or current Finnhub fundamental is
part of the model request.

## Proposed internal response

Use the exact fields currently produced by `src/model_training/phase9_prediction.py`:

```json
{
  "session_date": "2024-05-30",
  "decision_time": "after_close",
  "horizon_trading_sessions": 20,
  "evidence_status": "development_only",
  "return_model_version": "phase9_return_v1",
  "risk_model_version": "phase9_risk_v1",
  "predictions": [
    {
      "ticker": "AAPL",
      "return_class": "Middle",
      "return_probabilities": {"Lower": 0.31622179352795793, "Middle": 0.3631592128539408, "Higher": 0.3206189936181012},
      "return_rank_score": 0.004397200090143272,
      "risk_class": "Low",
      "risk_probabilities": {"Low": 0.4478840178147259, "Medium": 0.4014692467767355, "High": 0.15064673540853857},
      "return_rank": 36
    }
  ]
}
```

The AAPL prediction is the saved, measured **2024-05-30 historical fixture**;
the full response contains 50 predictions, of which one is shown. It is a
reproducibility fixture, not a new accuracy result. In every response each
probability is finite and in `[0, 1]`, and each three-class
group sums to one. The ranked list is sorted by `return_rank_score` descending
and ticker ascending on ties. The score is `P(Higher)-P(Lower)`, not expected
percentage gain. Risk probabilities represent Low/Medium/High future
20-session realized-volatility classes; the stored training cutoffs define
historical target labels, not Shariah limits. Probabilities are uncalibrated.
The backend may wrap the response inside its existing
`{success,statusCode,message,data}` format, but should not rename classes,
recompute ranks, or present research predictions as verified advice.

## Error and availability behavior

| Condition | AI route | Backend-facing behavior |
| --- | --- | --- |
| Malformed dates, duplicate keys, unknown ticker, missing/nonfinite bar, missing SPY, incomplete history/roster | 422 with stable error code and safe detail | 400/422 validation response; no prediction payload |
| Adjusted-price basis, dated roster, or after-close availability cannot be established | 422 or 503 `INPUT_UNAVAILABLE` | Show prediction unavailable; do not substitute raw `close` or guessed roster |
| Model artifact absent/hash mismatch or incompatible version | 503 `MODEL_UNAVAILABLE` | 503; no momentum or trailing-volatility fallback |
| AI service unreachable/times out | N/A | 502/503 from Node, with a bounded timeout and no invented result |

The AI route should not include Shariah compliance or portfolio weights. The
backend's compliance result remains a **separate** system, and any later
portfolio recommendation requires an approved Shariah methodology. User
`risk_preference` should affect later portfolio construction, not the model's
Low/Medium/High definitions.

## Current backend gap review

| Needed for AI request | Current HalalifyAPI checkout | Required preparation |
| --- | --- | --- |
| 61-session, 45–50-stock adjusted-close panel | `market_data` stores per-stock OHLCV and a `close` field; `/stocks/:id/market-data` reads one stock, defaulting to 90 calendar days | Add a versioned, documented all-adjusted price source and full-panel query. Do not equate stored `close` with training `adjusted_close` without proof. |
| Same-date SPY returns | No SPY benchmark row/return in the inspected `market_data` model and ingestion flow | Ingest/derive SPY on the same price basis and session calendar. |
| Historical ticker roster | `stocks.is_active` describes current DB status | Supply a dated roster; current active stocks cannot reconstruct historical membership. |
| Provider compatibility | Historical backfill requests `adjustment=all`, `feed=iex`; selected training snapshot uses Alpaca SIP | Record feed/adjustment/version and assess training-serving shift before using live backend bars. |
| AI client and route | No AI client or prediction route found in `src/routes`/`src/services` | Add bounded-timeout client, validation, errors, and Swagger contract after the input adapter is defined. |
| Model features | Backend `features` table holds current fundamental/technical JSON fields | Do not map those fields into the 17/7 market feature orders; AI reconstructs features from bars. |
| Shariah screening | Backend currently has separate hard-coded compliance configuration | Do not merge its output with prediction response or treat those thresholds as an approved AI methodology. Review separately before portfolio claims. |

The backend currently has no automated test gate (`npm test` is a placeholder).
Its `.env.example` also contains a commented password-like value; the backend
team should review that template without copying any credential into code or
the integration contract.
The present 9.8 scope can implement and test the **internal FastAPI route**
against a verified historical fixture. A live Node-to-AI path is blocked
until the backend provides the adjusted panel, SPY series, dated roster, and
availability evidence. Its public route and authentication choice remain a
backend-team decision.

## Evidence and limitations

The return and risk packages are `phase9_return_v1` and `phase9_risk_v1`.
Step 9.7 verified deterministic historical inference on 2016, 2021, and
2024 fixtures, but did not run an untouched post-fit performance test. The
current models are market-only, `development_only`, with source-quality and
historical-universe limits. SEC and sentiment are not model inputs. This
contract does not promote the models to production investment advice.
