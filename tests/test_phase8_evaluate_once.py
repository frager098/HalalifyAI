import json
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from src.model_training.phase8.evaluate_once import (
    numeric_distribution,
    run_one_time_evaluation,
)
from src.model_training.phase8.procedure import validate_runtime_gate


def test_colab_runtime_gate_needs_only_frozen_runtime_artifacts():
    result = validate_runtime_gate()
    assert result["passed"] is True
    assert result["reserved_outcome_values_read"] is False
    assert result["ready_for_one_time_evaluation"] is True


def test_declared_numeric_distribution_is_deterministic():
    result = numeric_distribution(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert result == {
        "count": 4,
        "mean": 2.5,
        "sample_std": pytest.approx(1.2909944487358056),
        "minimum": 1.0,
        "q25": 1.75,
        "median": 2.5,
        "q75": 3.25,
        "maximum": 4.0,
    }


def test_one_time_evaluator_refuses_overwrite_before_any_input_read():
    with tempfile.TemporaryDirectory(dir=".") as folder:
        output = Path(folder) / "evaluation.json"
        output.write_text(json.dumps({"existing": True}), encoding="utf-8")
        with pytest.raises(FileExistsError):
            run_one_time_evaluation(
                root=Path("."),
                procedure_path=Path("missing-procedure.json"),
                dataset_dir=Path("missing-dataset"),
                output_path=output,
            )
