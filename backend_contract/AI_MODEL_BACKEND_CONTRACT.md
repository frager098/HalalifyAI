# AI prediction response contract (draft v1)

This is the proposed contract between `HalalifyAI` (Python/FastAPI) and
`HalalifyAPI` (Node/Express). It lets backend work start before the trained
models are exposed through an inference endpoint. The required execution order
is Shariah screening first, followed by prediction for compliant stocks only.

## Proposed endpoint

`POST /v1/analyze`

Request:

```json
{
  "as_of_date": "2026-10-23",
  "tickers": ["AAPL", "MSFT", "NVDA"]
}
```

- `as_of_date` is the market session for which features are available.
- `tickers` contains uppercase U.S. equity symbols from the supported universe.
- The prediction horizon is fixed at 20 future trading sessions for v1.
- The AI service screens every requested ticker first. It invokes the models
  only for tickers that pass screening.

The complete dummy response is in
[`ai_prediction_response.example.json`](./ai_prediction_response.example.json).

## Required execution sequence

1. Validate the request and load point-in-time market/fundamental inputs.
2. Apply the configured, versioned Shariah screening methodology.
3. Separate compliant stocks from screened-out stocks.
4. Generate model features for compliant stocks.
5. Run return and risk inference for compliant stocks only.
6. Return both the screened-out records and successful predictions to the
   backend.

## Prediction item

Each ticker produces these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `ticker` | string | Uppercase stock symbol. |
| `screening` | object | The passing Shariah result used before inference. |
| `return_prediction.class_code` | 0, 1, or 2 | `0=lower`, `1=middle`, `2=higher`. |
| `return_prediction.class_label` | string | Predicted peer-relative return class. |
| `return_prediction.probabilities` | object | Probabilities for `lower`, `middle`, and `higher`. |
| `return_prediction.rank_score` | number | `P(higher) - P(lower)`, in the range `[-1, 1]`. Higher is preferred for ranking. |
| `risk_prediction.class_code` | 0, 1, or 2 | `0=low`, `1=medium`, `2=high`. |
| `risk_prediction.class_label` | string | Predicted fixed-band volatility class. |
| `risk_prediction.probabilities` | object | Probabilities for `low`, `medium`, and `high`. |
| `error` | object or null | Per-ticker inference failure details. Null when prediction succeeds. |

`screened_out` contains requested stocks that failed Shariah screening. Those
items contain the screening result and have no return or risk prediction.

## Contract rules

- Every probability is between 0 and 1. The three probabilities for one task
  sum to 1, allowing for minor floating-point tolerance.
- `class_code` and `class_label` identify the class with the greatest
  probability.
- Return and risk are separate predictions. In particular, `higher` return
  does not mean `high` risk.
- In the current research design, return labels mean lower/middle/higher
  relative to the fixed reference universe used during training. Screening
  first at inference does not redefine `higher` to mean "higher only among
  today's compliant stocks." That alternate meaning would require a revised
  target design and retraining.
- `rank_score` is an ordering signal, **not an expected percentage return**.
  Do not store or use it as `expected_return` in a mean-variance optimizer.
- Risk classes use model-version-specific boundaries learned from training
  data. They must not be recalculated from the current request's stocks.
- Shariah screening always runs before inference. A non-compliant stock must
  never be sent into the prediction step.
- The backend receives the screening result alongside each prediction and a
  separate `screened_out` collection for rejected stocks.
- The screening methodology and thresholds must be explicitly approved and
  versioned; this draft does not invent them.
- The backend should persist `as_of_date`, `generated_at`, model versions, and
  `schema_version` with predictions for auditability.
- A response can contain successful predictions, screened-out stocks, and
  compliant stocks whose features were unavailable. The backend should not
  fail the entire batch because one ticker cannot be predicted.

## Important current limitation

The values in the example response are fabricated contract fixtures, not
research results. As of this draft, the research review has not selected a
final return model. The placeholder model versions must be replaced when
production artifacts are approved, but the response shape can remain stable.

## Suggested public backend envelope

If the Node backend exposes this data to the frontend, it can place the AI
response inside its existing standard envelope:

```json
{
  "success": true,
  "statusCode": 200,
  "message": "Predictions retrieved successfully",
  "data": {
    "schema_version": "1.0",
    "request_id": "pred_dummy_20261023_001",
    "predictions": []
  }
}
```

The AI service itself does not need to add this Node-specific envelope.
