import json
from pathlib import Path
import tempfile

import pytest

from src.model_training.phase8.contract import load_contract, validate_contract


CONTRACT = Path("configs/phase8_evaluation_contract_v1.json")


def test_phase8_contract_reproduces_inputs_training_role_and_cutoffs():
    result = validate_contract(CONTRACT)
    assert result["passed"] is True
    assert result["outcomes_inspected"] is False
    assert result["training_rows"] == 120987
    assert result["phase7_selections_reproduced"] is True


def test_contract_keeps_reserved_dates_out_of_training():
    contract = load_contract(CONTRACT)
    chronology = contract["chronology"]
    assert chronology["last_training_target_window_end"] < chronology["reserved_evaluation_start"]
    assert chronology["reserved_evaluation_end"] < chronology["twentieth_support_session"]


def test_only_selected_benchmark_features_can_be_scored():
    contract = load_contract(CONTRACT)
    assert contract["feature_contract"]["scoring_allowlist"] == {
        "return": ["momentum_20d"],
        "risk": ["volatility_20d"],
    }
    assert contract["selected_procedures"]["return"]["fit"] == "none"
    assert "no learned estimator" in contract["selected_procedures"]["risk"]["fit"]


def test_hard_risk_benchmark_does_not_claim_probability_metrics():
    contract = load_contract(CONTRACT)
    statement = contract["reported_metrics"]["risk"]["probability_metrics"]
    assert "not applicable" in statement
    assert "must not be fabricated" in statement


def test_contract_rejects_a_claim_that_outcomes_were_inspected():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract["outcomes_inspected"] = True
    with tempfile.TemporaryDirectory(dir=".") as folder:
        path = Path(folder) / "contract.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        with pytest.raises(ValueError, match="outcomes"):
            load_contract(path)
