# Simplified data workflow

This refactor simplifies the approved `develop` data code. It preserves the
research calculations, source evidence and Shariah rules. It does not merge or
rewrite the separate `feature/model-evaluation` experiment.

## Normal use

Activate the project environment and install the existing cleaning/calendar
dependencies with `pip install -r requirements-cleaning.txt`. Run from the
repository root:

```bash
python -m src.data.pipeline
```

The command prints four stages: clean, validate, build, independently verify.
Each run gets a new version, preserving previous outputs. Add `--version
MY_NEW_VERSION` to choose a new version, or `--plan` to inspect the workflow
without reading data or writing outputs.

The default reuses the audited snapshot registered in
`configs/data_pipeline.json`: `data/interim/prices/price_repair_20261020/audited_prices.csv`,
SHA-256 `3eff4484f22a4e9b5c921541adbadfe3b37022a0d11c52c4742af3fbd7767df1`.
This generated file is shared separately from Git. A different checksum stops
the run. Registering another input is a data-version decision needing source
review; the workflow never silently chooses a newer file or another provider.

The workflow retains missing history and false evidence flags. It checks the
exchange calendar, does not invent earlier LIN history, and excludes affected
feature/target windows through the existing builders. It reuses the previous
source audit rather than re-downloading data or rerunning that raw/action audit.
For new source data, perform the explicit `price_audit` checks first.

## Outputs

| Location | Purpose |
| --- | --- |
| `data/interim/prices/VERSION/` | Derived cleaned prices and quarantined rows |
| `data/processed/VERSION/` | Research rows, full feature/target audit and metadata |
| `reports/validation/VERSION/` | Coverage, cleaning passes, independent checks, log and manifest |

`pipeline_manifest.json` records input/configuration/derived checksums, counts,
false flags and verification status. A failure after report creation leaves
`FAILED.json` identifying the failed stage. Original inputs and previous versions
are preserved. Completion does not establish full historical issuer/action
certification, Shariah eligibility or improved model accuracy.

## Main files

| File | Responsibility |
| --- | --- |
| `pipeline.py` | One offline entry point for registered price research |
| `download_alpaca.py` | Existing standalone company-price downloader; not called by the offline workflow |
| `sec.py` | SEC download, candidate extraction, supplementary collection and original-filing cross-check commands |
| `screening_disclosures.py` | Original report parsing and note inventory |
| `clean_data.py` | Existing cleaning functions and full-snapshot cleaner |
| `validate_data.py` | Existing broad source-data audit |
| `price_audit.py` | Schema checks, saved action reconciliation and strict audited-input checks |
| `build_price_research.py` | Existing 16-feature/20-session research builder |
| `verify_price_research.py` | Independent target/split/threshold verification |
| `reconciliation.py` | Shared cohort, checksum and JSON helpers |

The builder and independent checker remain separate. Shariah decisions stay
under `src/screening`; settings and limits stay under `configs`. SEC extracts are
candidates, not automatically approved totals or model predictors.

The old full-snapshot cleaner retains its `data/cleaned` output contract for
compatibility; no existing data was moved. New normal-workflow outputs use the
plan's section 6.1 locations above. Historical reports and recorded identifiers
remain historical evidence.

## Previous names and replacement commands

| Previous module | Replacement |
| --- | --- |
| `training_inputs`, `check_price_actions`, `price_schema` | `src.data.price_audit` |
| `download_sec`, `extract_sec_fundamentals`, `collect_screening_fields`, `check_screening_api` | `src.data.sec` subcommands `download`, `extract`, `collect`, `check` |
| `recover_screening_notes` | `src.data.screening_disclosures` |
| `collect_external_candidates` | `src.data.research.collect_external_candidates` |
| `review_kaggle_financials` | `src.data.research.review_kaggle_financials` |

Old module paths are replaced, not retained as duplicate wrappers. Repository
callers, tests, notebook imports and reproduction commands are updated. External
scripts with old imports must use this map. Investigation tools remain available
but are not required for the normal workflow.

The Colab notebook accepts the consolidated audit module or the previously
published module during migration, since its clone step still uses develop.
Both routes require the same strict audited-input checks. No missing-data or
verification-flag fallback is introduced. Code cells were syntax checked;
complete Colab installation/training was not rerun for this refactor.

Explicit source-work commands:

```bash
python -m src.data.price_audit --prices DUAL_BASIS_CSV --raw RAW_REFERENCE_CSV --actions SAVED_ACTION_FOLDER --repo .
python -m src.data.price_audit actions --prices DUAL_BASIS_CSV --raw RAW_REFERENCE_CSV --actions SAVED_ACTION_FOLDER --repo .
python -m src.data.sec download --out data/raw/NEW_SEC_DOWNLOAD
python -m src.data.sec extract --input data/raw/NEW_SEC_DOWNLOAD --out data/interim/NEW_SEC_EXTRACT
python -m src.data.sec collect --repo . --out data/raw/NEW_API_SNAPSHOT
python -m src.data.sec check --api API_SNAPSHOT --notes ORIGINAL_NOTE_INVENTORY --out reports/validation/NEW_CROSSCHECK.json
python -m src.data.screening_disclosures --repo . --archive ORIGINAL_REPORT_ZIP --out data/interim/NEW_NOTE_INVENTORY
```

The original SEC downloader additionally needs its existing `requests`
dependency. Downloads are explicit network operations; imports, help and the
normal workflow do not fetch data. New SEC downloads/extracts refuse existing
destination contents to protect retained evidence.

The broad validator and full-snapshot cleaner remain available because their
SEC coverage differs from the normal price-only workflow. A price check does not
replace them. Screening still uses the separate source-bound configuration.

## Verification

The original baseline passed 81 tests. Consolidated code passes 91 tests,
including input tampering, unknown evidence, preserved outputs, imports without
network calls and SEC extraction checks. The normal workflow was executed on
the actual registered local input. Its 118,643-row research CSV and 125,700-row
full audit CSV are byte-for-byte identical to a separate pre-refactor build in
the same Python 3.12 environment. Every retained target was independently
recomputed, including split purges and training-only thresholds. This verifies
refactor equivalence; it is not new training or improved accuracy. Fresh-checkout
checks are recorded separately from dependency-install claims. All 91 tests
also passed from a fresh exported source tree using the original project's
Python 3.13.7 environment. This did not install or upgrade project dependencies.

The full retained-source Shariah run was also repeated. All 50 complete company
records exactly match the published V6 records: 21 initial-filter failures,
29 needing review and zero complete passes. The existing independent screening
verifier confirms the decisions, ratios, bounds, business evidence and source
availability. Reorganisation did not resolve those outstanding evidence gaps.
