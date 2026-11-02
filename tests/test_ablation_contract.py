import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import pytest

from src.model_training.feature_ablation.ablation_contract import (
    DEFAULT_PROTOCOL,
    ContractMismatchError,
    build_ablation_contract_report,
    write_ablation_contract_report,
)


@pytest.fixture(scope="module")
def verified_report():
    return build_ablation_contract_report()


def test_contract_records_frozen_inputs_folds_and_questions(verified_report):
    assert verified_report["status"] == "verified"
    assert len(verified_report["development_folds"]) == 4
    assert len(verified_report["feature_allowlist"]) == 14
    assert verified_report["dataset"]["eligible_rows"] == {
        "return": 118987,
        "risk": 118987,
    }
    assert set(verified_report["research_questions"]) == {"return", "risk"}
    assert verified_report["research_questions"]["return"]["baseline"] == "momentum_20d_rank"
    assert (
        verified_report["research_questions"]["risk"]["baseline"]
        == "trailing_volatility_20d_with_fold_risk_cutoffs"
    )


def test_protocol_hash_mismatch_stops_before_report_is_built(tmp_path):
    changed_protocol = tmp_path / "changed_protocol.json"
    protocol = json.loads(DEFAULT_PROTOCOL.read_text(encoding="utf-8"))
    protocol["test_start"] = "2099-01-01"
    changed_protocol.write_text(json.dumps(protocol), encoding="utf-8")

    with pytest.raises(ContractMismatchError, match="protocol SHA-256 mismatch"):
        build_ablation_contract_report(protocol_path=changed_protocol)


def test_writer_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "ablation_contract.json"
    output.write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_ablation_contract_report(output)

    assert output.read_text(encoding="utf-8") == "preserve"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
