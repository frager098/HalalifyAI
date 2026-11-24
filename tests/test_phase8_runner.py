import json
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from src.model_training.phase8.runner import (
    evaluate_reserved_once,
    return_benchmark_metrics,
    risk_benchmark_metrics,
)
from src.model_training.phase8.validate_runner import (
    DEFAULT_DATASET_DIR,
    RESERVED_OUTCOME_COLUMNS,
    SAFE_AUDIT_COLUMNS,
    audit_real_inputs_without_outcomes,
    synthetic_runner_checks,
    validate_runner,
)


CONTRACT_PATH = Path("configs/phase8_evaluation_contract_v1.json")


def test_real_runner_audit_never_loads_reserved_outcome_columns():
    assert set(SAFE_AUDIT_COLUMNS).isdisjoint(RESERVED_OUTCOME_COLUMNS)
    result = audit_real_inputs_without_outcomes(
        root=Path("."), contract_path=CONTRACT_PATH, dataset_dir=DEFAULT_DATASET_DIR
    )
    assert result["reserved_outcome_values_read"] is False
    assert result["reserved_rows"] == 9350
    assert result["training_reserved_separation_valid"] is True


def test_synthetic_runner_is_deterministic_and_uses_no_probabilities():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    result = synthetic_runner_checks(contract)
    assert all(result.values())


def test_return_ties_use_ticker_order_for_deterministic_top_ten():
    rows = pd.DataFrame(
        {
            "ticker": [f"T{number:02d}" for number in range(12)],
            "session_date": ["2020-01-02"] * 12,
            "return_next_20d": list(range(12)),
            "momentum_20d": [1.0] * 12,
        }
    )
    result = return_benchmark_metrics(rows)
    assert result["defined_spearman_dates"] == 0
    assert result["daily"][0]["top10_forward_return"] is None


def test_risk_runner_rejects_saved_classes_that_differ_from_cutoffs():
    rows = pd.DataFrame(
        {
            "ticker": ["A"],
            "session_date": ["2020-01-02"],
            "risk_volatility_next_20d": [0.1],
            "risk_class": [2],
            "volatility_20d": [0.1],
        }
    )
    with pytest.raises(ValueError, match="Saved risk classes"):
        risk_benchmark_metrics(rows, [0.2, 0.3])


def test_validation_writes_no_score_evidence_and_refuses_overwrite():
    with tempfile.TemporaryDirectory(dir=".") as folder:
        output = Path(folder) / "runner_validation.json"
        result = validate_runner(
            root=Path("."),
            contract_path=CONTRACT_PATH,
            dataset_dir=DEFAULT_DATASET_DIR,
            output_path=output,
        )
        assert result["reserved_outcome_values_read"] is False
        assert result["evaluation_output_created"] is False
        with pytest.raises(FileExistsError):
            validate_runner(
                root=Path("."),
                contract_path=CONTRACT_PATH,
                dataset_dir=DEFAULT_DATASET_DIR,
                output_path=output,
            )


def test_real_evaluation_refuses_existing_output_before_reading_dataset():
    with tempfile.TemporaryDirectory(dir=".") as folder:
        output = Path(folder) / "result.json"
        output.write_text("existing", encoding="utf-8")
        with pytest.raises(FileExistsError):
            evaluate_reserved_once(
                dataset_path=Path("missing.csv"),
                metadata_path=Path("missing.json"),
                contract={},
                output_path=output,
            )
