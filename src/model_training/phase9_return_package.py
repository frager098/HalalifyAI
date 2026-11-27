"""Build and verify the Phase 9 research return package without refitting."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _probabilities(model: Pipeline, features: list[str], values: list[float]) -> list[float]:
    if len(values) != len(features) or not np.isfinite(values).all():
        raise ValueError("Fixture does not match finite feature order")
    frame = pd.DataFrame([values], columns=features)
    probabilities = model.predict_proba(frame)[0]
    if not np.isfinite(probabilities).all() or not np.isclose(probabilities.sum(), 1):
        raise ValueError("Invalid return probabilities")
    return probabilities.tolist()


def build_return_package(output: Path) -> dict:
    """Copy the exact fitted model; write a fixed feature fixture and provenance."""
    if output.exists():
        raise FileExistsError(f"Preserve existing package: {output}")
    source_root = Path("reports/model_evaluation/phase9_final_fit_v1")
    source = source_root / "return_model.joblib"
    fit_manifest_path = source_root / "manifest.json"
    validation_path = Path("reports/model_evaluation/phase9_package_input_validation_v2/validation_report.json")
    contract_path = Path("configs/phase9_inference_contract_v1.json")
    fit = json.loads(fit_manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if validation["status"] != "pass_research_inputs_with_disclosed_limitations" or validation["counts"]["failed"]:
        raise ValueError("Phase 9.3 research-input gate has not passed")
    if sha256(source) != fit["artifacts"]["return"]["sha256"]:
        raise ValueError("Fitted return artifact hash changed")
    if sha256(contract_path) != fit["input_sha256"]["inference_contract"]:
        raise ValueError("Inference contract changed")
    info = fit["final_fit"]["return"]
    features = info["feature_order"]
    classes = info["class_order"]
    if features != contract["return"]["feature_order"] or classes != ["Lower", "Middle", "Higher"]:
        raise ValueError("Return feature or class contract mismatch")
    model = joblib.load(source)
    if (not isinstance(model, Pipeline) or len(model.steps) != 2
            or not isinstance(model[0], StandardScaler)
            or not isinstance(model[-1], LogisticRegression)
            or not np.array_equal(model[-1].classes_, [0, 1, 2])
            or model[-1].n_features_in_ != len(features)
            or int(model[0].n_samples_seen_) != info["training"]["rows"]):
        raise ValueError("Fitted return pipeline differs from recorded specification")
    dataset_path = Path("data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv")
    if sha256(dataset_path) != fit["input_sha256"]["dataset"]:
        raise ValueError("Frozen fixture dataset changed")
    rows = pd.read_csv(dataset_path, usecols=["ticker", "session_date", "return_eligible", *features])
    candidates = rows.loc[rows.return_eligible & rows.session_date.eq(info["training"]["last_session"])]
    candidates = candidates.sort_values("ticker")
    if candidates.empty:
        raise ValueError("No final training-date fixture row")
    fixture_row = candidates.iloc[0]
    values = [float(fixture_row[name]) for name in features]
    probabilities = _probabilities(model, features, values)
    fixture = {"ticker": str(fixture_row.ticker), "session_date": str(fixture_row.session_date),
               "feature_order": features, "values": values}
    expected = {"class_codes": [0, 1, 2], "class_order": classes,
                "probabilities": probabilities, "rank_score": probabilities[2] - probabilities[0]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    packaged = output / "return_model.joblib"
    shutil.copyfile(source, packaged)
    if sha256(packaged) != sha256(source):
        raise ValueError("Package copy differs from fitted artifact")
    (output / "fixture_input.json").write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    (output / "fixture_expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "model_version": "phase9_return_v1",
                "evidence_status": "development_only", "model_kind": "LogisticRegression",
                "preprocessing": "fitted StandardScaler inside joblib Pipeline",
                "feature_order": features, "class_codes": [0, 1, 2], "class_order": classes,
                "rank_score": "P(Higher)-P(Lower)", "expected_percentage_return_supported": False,
                "training": info["training"], "selected_parameters": info["selected_parameters"],
                "selection_validation": fit["selection"]["return"],
                "dependencies": fit["dependencies"],
                "source_final_fit_manifest_sha256": sha256(fit_manifest_path),
                "source_model_sha256": sha256(source),
                "inference_contract_sha256": sha256(contract_path),
                "phase9_3_validation_sha256": sha256(validation_path),
                "package_model_sha256": sha256(packaged),
                "fixture_input_sha256": sha256(output / "fixture_input.json"),
                "fixture_expected_sha256": sha256(output / "fixture_expected.json"),
                "evaluation_reference": "Phase 7 outer-fold development reports and Phase 9.2b comparisons; no untouched post-fit test",
                "limitations": ["Market-only research model", "No Shariah result", "Source-quality and historical provenance limits remain disclosed"]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_return_package(output: Path) -> dict:
    """Load in a fresh process and compare probabilities with the fixed fixture."""
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, key in (("return_model.joblib", "package_model_sha256"),
                      ("fixture_input.json", "fixture_input_sha256"),
                      ("fixture_expected.json", "fixture_expected_sha256")):
        if sha256(output / name) != manifest[key]:
            raise ValueError(f"Changed packaged file: {name}")
    fixture = json.loads((output / "fixture_input.json").read_text(encoding="utf-8"))
    expected = json.loads((output / "fixture_expected.json").read_text(encoding="utf-8"))
    if fixture["feature_order"] != manifest["feature_order"] or expected["class_order"] != manifest["class_order"]:
        raise ValueError("Fixture order differs from package")
    model = joblib.load(output / "return_model.joblib")
    actual = _probabilities(model, manifest["feature_order"], fixture["values"])
    if not np.allclose(actual, expected["probabilities"], rtol=0, atol=1e-12):
        raise ValueError("Fresh-process probabilities differ")
    return {"model_version": manifest["model_version"], "fixture_ticker": fixture["ticker"],
            "fixture_date": fixture["session_date"], "probabilities": actual,
            "rank_score": actual[2] - actual[0], "verified": True}
