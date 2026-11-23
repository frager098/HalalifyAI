from pathlib import Path

import pytest

from src.model_training.feature_ablation.feature_inventory import sha256
from src.notebook_environment import ensure_phase5_dataset


def test_sha256_reads_file_in_binary_mode(tmp_path: Path) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"HalalifyAI\r\n")

    assert sha256(path) == "62dbc60a00ea094665e6755a3a1fefd689252d8ed7396df9d99504651ef875a8"


def test_existing_mismatched_dataset_is_never_overwritten(tmp_path: Path) -> None:
    dataset = (
        tmp_path
        / "data/processed/model_inputs/market_features_and_labels_v1/market_features_and_labels.csv"
    )
    dataset.parent.mkdir(parents=True)
    dataset.write_text("wrong dataset", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Existing Phase 5 dataset differs"):
        ensure_phase5_dataset(tmp_path)

    assert dataset.read_text(encoding="utf-8") == "wrong dataset"
