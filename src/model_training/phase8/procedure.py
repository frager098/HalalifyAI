"""Validate the no-fit Phase 8 procedure freeze without reserved outcomes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.model_training.phase8.build_reserved_dataset import sha256
from src.model_training.phase8.contract import validate_contract


DEFAULT_PROCEDURE = Path("configs/phase8_procedure_freeze_v1.json")


def validate_procedure_freeze(
    path: Path = DEFAULT_PROCEDURE, root: Path = Path(".")
) -> dict[str, Any]:
    root = root.resolve()
    path = (root / path).resolve() if not path.is_absolute() else path
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if freeze.get("status") != "frozen_ready_for_one_time_reserved_evaluation":
        raise ValueError("Phase 8 procedure is not frozen for evaluation")
    if (
        freeze.get("reserved_outcome_values_read")
        or freeze.get("model_fitting_performed")
        or freeze.get("model_artifacts_created")
        or freeze.get("selection_reopened")
    ):
        raise ValueError("No-fit Phase 8 procedure contains an invalid state claim")
    for identity in freeze["identities"].values():
        artifact = root / identity["path"]
        if not artifact.is_file() or sha256(artifact) != identity["sha256"]:
            raise ValueError(f"Procedure identity mismatch: {identity['path']}")

    contract_result = validate_contract(
        Path(freeze["identities"]["evaluation_contract"]["path"]), root
    )
    contract = json.loads(
        (root / freeze["identities"]["evaluation_contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    runner_validation = json.loads(
        (root / freeze["identities"]["runner_validation"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if runner_validation.get("status") != "passed":
        raise ValueError("Step 8.4 runner validation did not pass")
    if (
        runner_validation.get("reserved_outcome_values_read")
        or runner_validation.get("performance_metrics_calculated_on_reserved_period")
        or runner_validation.get("evaluation_output_created")
    ):
        raise ValueError("Step 8.4 was not outcome-blind")

    selected = contract["selected_procedures"]
    if freeze["return_procedure"]["name"] != selected["return"]["name"]:
        raise ValueError("Frozen return procedure differs from the contract")
    if freeze["return_procedure"]["fit_action"] != "none":
        raise ValueError("Return benchmark must not fit parameters")
    if freeze["risk_procedure"]["name"] != selected["risk"]["name"]:
        raise ValueError("Frozen risk procedure differs from the contract")
    risk_contract = contract["label_contract"]["risk_classes"]
    saved_cutoffs = [
        freeze["risk_procedure"]["low_upper_inclusive"],
        freeze["risk_procedure"]["medium_upper_inclusive"],
    ]
    contract_cutoffs = [
        risk_contract["low_upper_inclusive"],
        risk_contract["medium_upper_inclusive"],
    ]
    if saved_cutoffs != contract_cutoffs:
        raise ValueError("Frozen risk cutoffs differ from the contract")
    if freeze["risk_procedure"]["cutoff_training_rows"] != contract_result["training_rows"]:
        raise ValueError("Frozen risk-cutoff training rows differ")
    if freeze["training_role"]["ticker_date_keys_sha256"] != contract_result["training_keys_sha256"]:
        raise ValueError("Frozen training role identity differs")

    return {
        "stage": "phase_8_step_8_5_procedure_validation",
        "passed": True,
        "reserved_outcome_values_read": False,
        "model_fitting_performed": False,
        "model_artifacts_created": False,
        "selection_reopened": False,
        "procedure_freeze_sha256": sha256(path),
        "contract_sha256": contract_result["contract_sha256"],
        "return_procedure": freeze["return_procedure"]["name"],
        "risk_procedure": freeze["risk_procedure"]["name"],
        "risk_cutoffs": saved_cutoffs,
        "ready_for_step_8_6": True,
    }


def validate_runtime_gate(
    path: Path = DEFAULT_PROCEDURE, root: Path = Path(".")
) -> dict[str, Any]:
    """Validate only artifacts required to run Step 8.6.

    This lighter gate is intended for Colab. It does not require the large
    pre-2026 development dataset because the full training-role reproduction
    was already frozen and validated in Steps 8.2 and 8.5.
    """
    root = root.resolve()
    path = (root / path).resolve() if not path.is_absolute() else path
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if freeze.get("status") != "frozen_ready_for_one_time_reserved_evaluation":
        raise ValueError("Phase 8 procedure is not ready for Step 8.6")
    if any(
        freeze.get(field)
        for field in (
            "selection_reopened",
            "reserved_outcome_values_read",
            "model_fitting_performed",
            "model_artifacts_created",
        )
    ):
        raise ValueError("Phase 8 procedure has an invalid runtime state")
    for name in ("evaluation_contract", "reserved_dataset", "runner_validation", "runner_code"):
        identity = freeze["identities"][name]
        artifact = root / identity["path"]
        if not artifact.is_file() or sha256(artifact) != identity["sha256"]:
            raise ValueError(f"Runtime identity mismatch: {identity['path']}")
    contract = json.loads(
        (root / freeze["identities"]["evaluation_contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    runner_validation = json.loads(
        (root / freeze["identities"]["runner_validation"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if runner_validation.get("status") != "passed" or any(
        runner_validation.get(field)
        for field in (
            "reserved_outcome_values_read",
            "performance_metrics_calculated_on_reserved_period",
            "evaluation_output_created",
        )
    ):
        raise ValueError("Step 8.4 runtime gate is invalid")
    contract_cutoffs = [
        contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
        contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
    ]
    frozen_cutoffs = [
        freeze["risk_procedure"]["low_upper_inclusive"],
        freeze["risk_procedure"]["medium_upper_inclusive"],
    ]
    if frozen_cutoffs != contract_cutoffs:
        raise ValueError("Runtime risk cutoffs differ from the contract")
    return {
        "passed": True,
        "procedure_freeze_sha256": sha256(path),
        "contract_sha256": freeze["identities"]["evaluation_contract"]["sha256"],
        "dataset_sha256": freeze["identities"]["reserved_dataset"]["sha256"],
        "runner_validation_sha256": freeze["identities"]["runner_validation"]["sha256"],
        "runner_code_sha256": freeze["identities"]["runner_code"]["sha256"],
        "risk_cutoffs": frozen_cutoffs,
        "reserved_outcome_values_read": False,
        "ready_for_one_time_evaluation": True,
    }
