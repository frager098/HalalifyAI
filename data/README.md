# Data layout

This directory contains datasets and generated data artifacts. It does not
contain Python source code.

- `raw/` contains immutable provider snapshots. Snapshot timestamps and page
  names such as `all_0001.json` are preserved because manifests and checksums
  depend on them.
- `interim/` contains normalized intermediate data derived from raw snapshots.
- `processed/cleaned_market_data/` contains validated market-cleaning runs.
- `processed/model_inputs/` contains feature tables and model-ready datasets.

Timestamped snapshot identifiers are provenance, not arbitrary IDs. Do not
rename files inside raw snapshots or edit their metadata in place.
