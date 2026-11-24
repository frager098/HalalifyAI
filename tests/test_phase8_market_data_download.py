import json
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from src.data_pipeline.download_phase8_market_data import (
    load_config,
    normalize_bars,
    validate_coverage,
)


def test_frozen_config_keeps_phase8_collection_separate():
    config = load_config(Path("configs/phase8_market_data_collection_v1.json"))
    assert config["evaluation_period"] == {"start": "2026-01-02", "end": "2026-09-30"}
    assert config["collection_period"]["start"] < config["evaluation_period"]["start"]
    assert config["collection_period"]["end"] > config["evaluation_period"]["end"]
    assert config["output_root"] == "data/raw/phase8_market"
    assert len(config["symbols"]) == 51


def test_load_config_rejects_a_period_without_supporting_dates():
    source = json.loads(Path("configs/phase8_market_data_collection_v1.json").read_text())
    source["collection_period"]["end"] = source["evaluation_period"]["end"]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "config.json"
        path.write_text(json.dumps(source))
        with pytest.raises(ValueError, match="surround"):
            load_config(path)


def test_normalization_preserves_split_bars_and_all_adjusted_close():
    split = [
        {"ticker": "AAPL", "t": "2026-01-02T05:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 100}
    ]
    adjusted = [
        {"ticker": "AAPL", "t": "2026-01-02T05:00:00Z", "o": 8, "h": 9, "l": 7, "c": 8.5, "v": 120}
    ]
    result = normalize_bars(split, adjusted, "phase8_test")
    assert result.loc[0, "close"] == 11
    assert result.loc[0, "volume"] == 100
    assert result.loc[0, "adjusted_close"] == 8.5
    assert result.loc[0, "dataset_version"] == "phase8_test"


def test_normalization_rejects_mismatched_adjustment_keys():
    split = [{"ticker": "AAPL", "t": "2026-01-02T05:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]
    with pytest.raises(ValueError, match="different keys"):
        normalize_bars(split, [], "phase8_test")
