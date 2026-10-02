# Data readiness: reviewed research snapshot

Updated 2026-10-02. This records executed work; it does not grant methodology or Shariah approval.

The isolated `feature/data-readiness` branch combines the published reconciliation and BAC identity work, then adds numerical price checks, the dictionary's 16 predictors, future 20-session targets, chronological splits, provisional model comparisons and a screening evidence handoff. It has not been merged into develop. Other developer review is still required.

## What changed

- Separate split-only close/volume and dividend-adjusted close are retained. A newly downloaded **raw** SIP reference checks the split price/volume relationship, split ratios and dividend adjustments within cent/share rounding tolerance.
- SPY remains a separate market reference. The original 50 companies are preserved; LIN's unavailable earlier history is never filled with made-up prices.
- The proposed revised observation period is 2016–2025. Features start after 60 complete return sessions. The original 2015 warm-up was unavailable from this source and remains a documented amendment requiring team acceptance.
- XOM predecessor evidence and BAC verified filing identity are retained. Financial components and alternatives remain evidence, not automatically approved debt totals or annual revenue.
- Incomplete price windows and windows crossing unresolved corporate actions are excluded. Raw files remain unchanged.
- Target thresholds use training rows only. Labels crossing the next split boundary are removed. Test performance is not used for model selection.

## Executed snapshot

127,501 market rows cover 50 companies plus SPY. Numerical share-basis checks pass. Five spin-off transitions remain unsupported: DHR 2023-10-02; GE 2019-02-25, 2023-01-04 and 2024-04-02; HON 2025-10-30. A spin-off gives shareholders shares in another company; a price change around it is not automatically a trading loss. We exclude affected feature/target windows rather than guess its value. This is not universal corporate-action certification.

| Partition | Usable company rows | Feature dates | Latest target end |
| --- | ---: | --- | --- |
| Training | 58,157 | 2016-03-31 through 2020-12-02 | 2020-12-31 |
| Validation | 24,150 | 2021-01-04 through 2022-12-01 | 2022-12-30 |
| Test, not scored | 36,336 | 2023-01-03 through 2025-12-02 | 2025-12-31 |

118,643 rows are usable; 7,057 calendar/company rows are excluded. Reports contain the detailed reasons. Validation is the middle period used to choose a model. The test period is reserved for one final evaluation after choices are frozen and reviewed.

## Reproduce from saved inputs

Use Python 3.12 and `pip install -r requirements.txt`. Run commands from the repository root. Replace paths with the actual saved run folders; never change the original raw files.

If the saved bundle is installed at the catalog paths, the short command is `python -m src.data.run_readiness`. Add `--train` to rerun the provisional comparisons. This command checks that all inputs exist before starting. For fresh-environment reproduction of the saved dataset and selected model fits, use `python -m src.evaluation.reproduce_readiness` after installing trusted local artifacts.

```text
python -m pytest
python -m src.data.check_price_actions --prices data/interim/prices/<run>/daily_prices.csv --raw data/raw/<raw-run>/raw_prices.csv --actions data/raw/actions/<action-run>
python -m src.data.build_research_dataset --prices data/interim/readiness_v1/audited_prices.csv
python -m src.models.train_candidates --dataset data/processed/core_v1_readiness/research_rows.csv
python -m src.data.prepare_screening_handoff --facts data/interim/sec_identity/<verified-run>/financial_facts_identity_updated.csv
```

For a new raw reference, use `python -m src.data.collect_raw_reference --prices <saved-price-csv> --output data/raw/<new-folder>`. It reads local Alpaca credentials from `.env`, saves exact pages and request metadata, and refuses to overwrite a folder. This is a new provider snapshot, not a promise of identical historical revisions.

## Outputs and limits

`data/interim/readiness_v1/` holds audited prices, feature/target audit rows and screening evidence. `data/processed/core_v1_readiness/research_rows.csv` is suitable for this provisional **price-based prediction** experiment, not an approved screened investment universe. `reports/validation/readiness_v1/` holds exclusions, calendar and thresholds. `reports/experiments/core_v1_readiness/` holds validation comparisons. `artifacts/core_v1_readiness/` contains local model files. Large data/models are ignored by Git; teammates need a separate data bundle or their own collection, with matching hashes.

The current after-close information cutoff assumes bar arrival; historical arrival timestamps were not collected. Daily bars retrieved today can contain later provider revisions. The cohort is today's selected 50 companies and has survivorship/selection bias. Symbols are provisional identifiers, not a certified historical security master. No claim of a fully historical point-in-time dataset is made.

## Still pending

The user confirmed on 2026-10-02 that no Shariah standard/edition has been selected. All approved screening metrics remain null and every company is ineligible pending evidence/rule review. TTM revenue (the latest four quarters), debt component mapping, interest-bearing securities, prohibited income and dated business activities still need the selected methodology. Missing evidence never means zero.

The plan/SRS versus proposed experiment disagreements about class definitions, horizon/cadence and source/warm-up require explicit project decisions. Models here classify return/volatility; they do not directly predict a percentage return or certify halal status. Final refit, untouched-test evaluation, probability calibration, backend contract agreement and portfolio backtesting are not completed. Neither code existence nor a clean Git status proves these milestones.
