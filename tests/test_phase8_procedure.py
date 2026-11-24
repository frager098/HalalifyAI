import json
from pathlib import Path
import tempfile

import pytest

from src.model_training.phase8.procedure import (
    DEFAULT_PROCEDURE,
    validate_procedure_freeze,
)


def test_no_fit_procedure_freeze_reproduces_every_identity():
    result = validate_procedure_freeze()
    assert result["passed"] is True
    assert result["model_fitting_performed"] is False
    assert result["model_artifacts_created"] is False
    assert result["reserved_outcome_values_read"] is False
    assert result["ready_for_step_8_6"] is True


def test_procedure_contains_no_estimator_artifact_or_parameter_search():
    freeze = json.loads(DEFAULT_PROCEDURE.read_text(encoding="utf-8"))
    assert freeze["return_procedure"]["model_artifact"] is None
    assert freeze["risk_procedure"]["model_artifact"] is None
    assert freeze["return_procedure"]["fitted_parameters"] == {}
    assert freeze["risk_procedure"]["fit_action"] == "reuse_frozen_training_only_cutoffs"


def test_procedure_rejects_a_false_fitting_claim():
    freeze = json.loads(DEFAULT_PROCEDURE.read_text(encoding="utf-8"))
    freeze["model_fitting_performed"] = True
    with tempfile.TemporaryDirectory(dir=".") as folder:
        path = Path(folder) / "invalid.json"
        path.write_text(json.dumps(freeze), encoding="utf-8")
        with pytest.raises(ValueError, match="invalid state"):
            validate_procedure_freeze(path)
