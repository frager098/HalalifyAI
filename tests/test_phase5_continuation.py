from pathlib import Path

from src.model_training.feature_ablation import phase5_continuation as continuation


def test_continuation_has_separate_identity_and_output_root() -> None:
    assert continuation.EXPERIMENT_ID == "phase6_phase5_continuation_v1"
    assert continuation.OUTPUT_ROOT == Path(
        "reports/model_evaluation/phase6_phase5_continuation_v1"
    )
    assert "phase6_recovery_v1" not in str(continuation.OUTPUT_ROOT)
    assert continuation.DATASET == Path(
        "data/processed/model_inputs/market_features_and_labels_v1/"
        "market_features_and_labels.csv"
    )


def test_momentum_wrapper_passes_continuation_inputs(monkeypatch) -> None:
    captured = {}

    def fake_writer(output, **kwargs):
        captured["output"] = output
        captured.update(kwargs)
        return {"status": "complete"}

    monkeypatch.setattr(
        continuation, "write_recovery_momentum_ablation_report", fake_writer
    )

    report = continuation.write_momentum_report()

    assert report["status"] == "complete"
    assert captured["output"] == continuation.MOMENTUM_OUTPUT
    assert captured["dataset_path"] == continuation.DATASET
    assert captured["metadata_path"] == continuation.METADATA
    assert captured["protocol_path"] == continuation.PROTOCOL
    assert captured["inventory_path"] == continuation.INVENTORY_JSON
    assert captured["evidence_mode"] == continuation.EVIDENCE_MODE


def test_friend_recovery_and_continuation_outputs_cannot_collide() -> None:
    continuation_outputs = {
        continuation.MOMENTUM_OUTPUT,
        continuation.VOLATILITY_OUTPUT,
        continuation.DOWNSIDE_TREND_OUTPUT,
        continuation.MARKET_RELATIVE_OUTPUT,
        continuation.VOLUME_OUTPUT,
    }
    assert len(continuation_outputs) == 5
    assert all("phase6_phase5_continuation_v1" in str(path) for path in continuation_outputs)
