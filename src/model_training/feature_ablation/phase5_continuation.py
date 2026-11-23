"""Phase 6 wrappers for the student's exact Phase 5 dataset lineage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.model_training.chronological_evaluation_protocol import run as build_protocol
from src.model_training.feature_ablation.ablation_runner import (
    write_recovery_downside_trend_ablation_report,
    write_recovery_market_relative_ablation_report,
    write_recovery_momentum_ablation_report,
    write_recovery_runner_validation_report,
    write_recovery_volatility_ablation_report,
    write_recovery_volume_ablation_report,
)
from src.model_training.feature_ablation.feature_inventory import (
    sha256,
    write_recovery_feature_inventory_report,
)


EXPERIMENT_ID = "phase6_phase5_continuation_v1"
EVIDENCE_MODE = "phase_5_continuation; original_phase_5_dataset_and_protocol_reproduced"
DATASET = Path(
    "data/processed/model_inputs/market_features_and_labels_v1/"
    "market_features_and_labels.csv"
)
METADATA = DATASET.with_name("dataset_metadata.json")
OUTPUT_ROOT = Path("reports/model_evaluation") / EXPERIMENT_ID
PROTOCOL = OUTPUT_ROOT / "chronological_evaluation_protocol.json"
INVENTORY_JSON = OUTPUT_ROOT / "feature_inventory.json"
INVENTORY_CSV = OUTPUT_ROOT / "feature_inventory.csv"
RUNNER_VALIDATION = OUTPUT_ROOT / "runner_validation.json"
MOMENTUM_OUTPUT = OUTPUT_ROOT / "momentum_ablation"
VOLATILITY_OUTPUT = OUTPUT_ROOT / "volatility_ablation"
DOWNSIDE_TREND_OUTPUT = OUTPUT_ROOT / "downside_trend_ablation"
MARKET_RELATIVE_OUTPUT = OUTPUT_ROOT / "market_relative_ablation"
VOLUME_OUTPUT = OUTPUT_ROOT / "volume_ablation"

EXPECTED_DATASET_SHA256 = "71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f"
EXPECTED_METADATA_SHA256 = "b36ed46ac5a68b74130b26df8f20d965928c53d62467c163a214f8b37fd35ba9"
EXPECTED_PROTOCOL_SHA256 = "048d82ce2ed0bedde60bd5f6215303fa86ebdab31aae5b5c330f0947372859ff"


def _assert_phase5_inputs() -> None:
    missing = [path for path in (DATASET, METADATA) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing Phase 5 continuation inputs: " + ", ".join(map(str, missing))
        )
    identities = {
        DATASET: EXPECTED_DATASET_SHA256,
        METADATA: EXPECTED_METADATA_SHA256,
    }
    for path, expected in identities.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(
                f"{path} is not the student's frozen Phase 5 artifact: "
                f"expected {expected}, found {actual}"
            )


def prepare_inputs() -> dict[str, Any]:
    """Reproduce the protocol, inventory, and no-fit validation once."""

    _assert_phase5_inputs()
    if not PROTOCOL.exists():
        build_protocol(DATASET, PROTOCOL)
    if sha256(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("Rebuilt Phase 4 protocol differs from the Phase 5 protocol")

    inventory, _ = write_recovery_feature_inventory_report(
        DATASET,
        METADATA,
        PROTOCOL,
        INVENTORY_JSON,
        INVENTORY_CSV,
        evidence_mode=EVIDENCE_MODE,
    )
    validation = write_recovery_runner_validation_report(
        RUNNER_VALIDATION,
        DATASET,
        METADATA,
        PROTOCOL,
        INVENTORY_JSON,
        evidence_mode=EVIDENCE_MODE,
    )
    return {"inventory": inventory, "validation": validation}


def _inputs() -> dict[str, Any]:
    return {
        "dataset_path": DATASET,
        "metadata_path": METADATA,
        "protocol_path": PROTOCOL,
        "inventory_path": INVENTORY_JSON,
        "evidence_mode": EVIDENCE_MODE,
    }


def write_momentum_report() -> dict[str, Any]:
    return write_recovery_momentum_ablation_report(MOMENTUM_OUTPUT, **_inputs())


def write_volatility_report() -> dict[str, Any]:
    return write_recovery_volatility_ablation_report(VOLATILITY_OUTPUT, **_inputs())


def write_downside_trend_report() -> dict[str, Any]:
    return write_recovery_downside_trend_ablation_report(
        DOWNSIDE_TREND_OUTPUT, **_inputs()
    )


def write_market_relative_report() -> dict[str, Any]:
    return write_recovery_market_relative_ablation_report(
        MARKET_RELATIVE_OUTPUT, **_inputs()
    )


def write_volume_report() -> dict[str, Any]:
    return write_recovery_volume_ablation_report(VOLUME_OUTPUT, **_inputs())


def experiment_summary() -> dict[str, Any]:
    """Return identities and completion state without fitting models."""

    return {
        "experiment_id": EXPERIMENT_ID,
        "dataset_sha256": sha256(DATASET) if DATASET.is_file() else None,
        "metadata_sha256": sha256(METADATA) if METADATA.is_file() else None,
        "protocol_sha256": sha256(PROTOCOL) if PROTOCOL.is_file() else None,
        "outputs": {
            "inventory": INVENTORY_JSON.is_file(),
            "runner_validation": RUNNER_VALIDATION.is_file(),
            "momentum": MOMENTUM_OUTPUT.is_dir(),
            "volatility": VOLATILITY_OUTPUT.is_dir(),
            "downside_trend": DOWNSIDE_TREND_OUTPUT.is_dir(),
            "market_relative": MARKET_RELATIVE_OUTPUT.is_dir(),
            "volume": VOLUME_OUTPUT.is_dir(),
        },
    }
