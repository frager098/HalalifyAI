"""Create the separately versioned Phase 6.9 market-feature expansion dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import pandas as pd

from src.feature_engineering.market_features import FEATURE_COLUMNS
from src.feature_engineering.phase6_expansion_features import (
    EXPANSION_FEATURE_COLUMNS,
    build_phase6_expansion_features,
)
from src.feature_engineering.build_feature_dataset import sha256


DEFAULT_SOURCE = Path(
    "data/processed/model_inputs/market_features_and_labels_v1/"
    "market_features_and_labels.csv"
)
DEFAULT_OUTPUT = Path("data/processed/model_inputs/phase6_expanded_features_v1")
EXPECTED_SOURCE_SHA256 = "71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f"
EXPECTED_METADATA_SHA256 = "b36ed46ac5a68b74130b26df8f20d965928c53d62467c163a214f8b37fd35ba9"
EXPANDED_FEATURE_COLUMNS = FEATURE_COLUMNS + EXPANSION_FEATURE_COLUMNS


def build_expanded_dataset(
    source: Path = DEFAULT_SOURCE,
    output: Path = DEFAULT_OUTPUT,
) -> dict:
    """Add six predeclared features without changing source rows or labels."""

    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError(output)
    metadata_path = source.with_name("dataset_metadata.json")
    if not source.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Phase 5 dataset and metadata are required")
    if sha256(source) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Phase 5 source dataset checksum mismatch")
    if sha256(metadata_path) != EXPECTED_METADATA_SHA256:
        raise ValueError("Phase 5 source metadata checksum mismatch")

    parent_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    original = pd.read_csv(source, low_memory=False)
    if original.duplicated(["ticker", "session_date"]).any():
        raise ValueError("Duplicate Phase 5 row keys")
    if parent_metadata.get("feature_columns") != FEATURE_COLUMNS:
        raise ValueError("Phase 5 feature allowlist differs from the frozen list")

    added = build_phase6_expansion_features(original)
    result = original.copy()
    for column in EXPANSION_FEATURE_COLUMNS:
        result[column] = added[column].to_numpy()
    pd.testing.assert_frame_equal(original, result[original.columns])

    originally_eligible = original["return_eligible"] | original["risk_eligible"]
    missing_eligible = result.loc[
        originally_eligible, EXPANSION_FEATURE_COLUMNS
    ].isna()
    if missing_eligible.any().any():
        counts = missing_eligible.sum().loc[lambda values: values.gt(0)].to_dict()
        raise ValueError(
            "Expansion would change Phase 5 eligible-row coverage: " f"{counts}"
        )
    result["phase6_expansion_features_complete"] = result[
        EXPANSION_FEATURE_COLUMNS
    ].notna().all(axis=1)

    metadata = dict(parent_metadata)
    metadata.update(
        stage="phase6_expanded_features_and_labels",
        dataset_version="phase6_expanded_features_v1",
        parent_dataset=source.as_posix(),
        parent_dataset_sha256=EXPECTED_SOURCE_SHA256,
        parent_metadata_sha256=EXPECTED_METADATA_SHA256,
        feature_columns=EXPANDED_FEATURE_COLUMNS,
        added_feature_columns=EXPANSION_FEATURE_COLUMNS,
        expansion_rule=(
            "Add only the predeclared Phase 6.9 cross-sectional relative-strength "
            "and SPY market-regime groups; preserve all rows, labels, splits, and "
            "original eligibility flags."
        ),
        missingness=result.isna().sum().astype(int).to_dict(),
        complete_feature_rows=int(
            result[EXPANDED_FEATURE_COLUMNS].notna().all(axis=1).sum()
        ),
        eligible_counts={
            task: int(result[f"{task}_eligible"].sum())
            for task in ("return", "risk")
        },
        excluded_from_features=[
            column for column in result if column not in EXPANDED_FEATURE_COLUMNS
        ],
        feature_definitions_source=(
            "src/feature_engineering/phase6_expansion_features.py"
        ),
    )
    metadata["code_sha256"] = {
        path: sha256(path)
        for path in (
            "src/target_engineering/build_phase6_expanded_dataset.py",
            "src/feature_engineering/phase6_expansion_features.py",
        )
    }

    output.mkdir(parents=True, exist_ok=False)
    destination = output / "market_features_and_labels.csv"
    result.to_csv(destination, index=False)
    metadata["output_sha256"] = sha256(destination)
    (output / "dataset_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    first = build_expanded_dataset(args.source, args.output_dir)
    with tempfile.TemporaryDirectory() as temporary:
        second = build_expanded_dataset(
            args.source, Path(temporary) / "reproduction"
        )
    comparable = {key: value for key, value in first.items() if key != "output_sha256"}
    reproduced = {key: value for key, value in second.items() if key != "output_sha256"}
    if comparable != reproduced or first["output_sha256"] != second["output_sha256"]:
        raise RuntimeError("Expanded dataset did not reproduce byte-for-byte")
    print(
        json.dumps(
            {
                "reproduced": True,
                "output": str(args.output_dir),
                "output_sha256": first["output_sha256"],
                "features": first["added_feature_columns"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
