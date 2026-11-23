# Data layout

This directory contains datasets and generated data artifacts. It does not
contain Python source code.

- `raw/` contains immutable provider snapshots. Snapshot timestamps and page
  names such as `all_0001.json` are preserved because manifests and checksums
  depend on them.
- `interim/` contains normalized intermediate data derived from raw snapshots.
- `processed/cleaned_market_data/` contains validated market-cleaning runs.
- `processed/model_inputs/` contains feature tables and model-ready datasets.

Phase 6.9 writes its student-generated expansion to
`processed/model_inputs/phase6_expanded_features_v1/`. It derives from the
frozen `market_features_and_labels_v1` parent, adds only the six predeclared
market features, and preserves every ordered key, class label, split, and
eligibility flag. A post-run audit found CSV round-trip noise in one continuous
return value (`3.4e-21`) and one continuous volatility value (`4.4e-16`); no
class, rank, cutoff, split, eligibility decision, or fold changed. The directory
is reproducible local evidence and must not replace or modify the Phase 5 parent
dataset.

Timestamped snapshot identifiers are provenance, not arbitrary IDs. Do not
rename files inside raw snapshots or edit their metadata in place.
