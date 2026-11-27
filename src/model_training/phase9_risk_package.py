"""Package the fitted Phase 9 risk model and its training-only class boundaries."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_realized_volatility(values: list[float], boundaries: list[float]) -> list[int]:
    """Apply the frozen training-derived Low/Medium/High target definition."""
    if len(boundaries) != 2 or not np.isfinite(boundaries).all() or boundaries[0] >= boundaries[1]:
        raise ValueError("Invalid risk boundaries")
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite realized volatility")
    return np.select([np.less_equal(values, boundaries[0]),
                      np.less_equal(values, boundaries[1])], [0, 1], default=2).tolist()


def _probabilities(model, features: list[str], values: list[float]) -> list[float]:
    if len(features) != len(values) or not np.isfinite(values).all():
        raise ValueError("Fixture does not match finite feature order")
    result = model.predict_proba(pd.DataFrame([values], columns=features))[0]
    if not np.isfinite(result).all() or not np.isclose(result.sum(), 1):
        raise ValueError("Invalid risk probabilities")
    return result.tolist()


def build_risk_package(output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Preserve existing package: {output}")
    source_root = Path("reports/model_evaluation/phase9_final_fit_v1")
    source = source_root / "risk_model.joblib"
    fit_path = source_root / "manifest.json"
    validation_path = Path("reports/model_evaluation/phase9_package_input_validation_v2/validation_report.json")
    contract_path = Path("configs/phase9_inference_contract_v1.json")
    fit = json.loads(fit_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if validation["status"] != "pass_research_inputs_with_disclosed_limitations" or validation["counts"]["failed"]:
        raise ValueError("Phase 9.3 research-input gate has not passed")
    if sha256(source) != fit["artifacts"]["risk"]["sha256"]:
        raise ValueError("Fitted risk artifact hash changed")
    if sha256(contract_path) != fit["input_sha256"]["inference_contract"]:
        raise ValueError("Inference contract changed")
    info = fit["final_fit"]["risk"]
    features, classes, boundaries = info["feature_order"], info["class_order"], info["risk_boundaries"]
    if features != contract["risk"]["feature_order"] or classes != ["Low", "Medium", "High"]:
        raise ValueError("Risk feature or class order differs from contract")
    model = joblib.load(source)
    if (not isinstance(model, HistGradientBoostingClassifier)
            or not np.array_equal(model.classes_, [0, 1, 2])
            or model.n_features_in_ != len(features)
            or model.early_stopping is not False
            or model.max_leaf_nodes != info["selected_parameters"]["max_leaf_nodes"]):
        raise ValueError("Fitted risk estimator differs from recorded specification")
    dataset_path = Path("data/processed/model_inputs/phase6_expanded_features_v1/market_features_and_labels.csv")
    if sha256(dataset_path) != fit["input_sha256"]["dataset"]:
        raise ValueError("Frozen fixture dataset changed")
    rows = pd.read_csv(dataset_path, usecols=["ticker", "session_date", "risk_eligible", *features])
    candidates = rows.loc[rows.risk_eligible & rows.session_date.eq(info["training"]["last_session"])].sort_values("ticker")
    if candidates.empty:
        raise ValueError("No final training-date risk fixture")
    row = candidates.iloc[0]
    values = [float(row[name]) for name in features]
    probabilities = _probabilities(model, features, values)
    boundary_values = [boundaries[0], float(np.nextafter(boundaries[0], np.inf)),
                       boundaries[1], float(np.nextafter(boundaries[1], np.inf))]
    boundary_classes = classify_realized_volatility(boundary_values, boundaries)
    if boundary_classes != [0, 1, 1, 2]:
        raise ValueError("Risk cutoff tie semantics changed")
    fixture = {"ticker": str(row.ticker), "session_date": str(row.session_date),
               "feature_order": features, "values": values,
               "boundary_test_values": boundary_values}
    expected = {"class_codes": [0, 1, 2], "class_order": classes,
                "probabilities": probabilities, "predicted_class_code": int(np.argmax(probabilities)),
                "boundary_class_codes": boundary_classes}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    packaged = output / "risk_model.joblib"
    shutil.copyfile(source, packaged)
    if sha256(packaged) != sha256(source):
        raise ValueError("Package copy differs from fitted risk artifact")
    (output / "fixture_input.json").write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    (output / "fixture_expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "model_version": "phase9_risk_v1", "evidence_status": "development_only",
                "model_kind": "HistGradientBoostingClassifier", "feature_order": features,
                "class_codes": [0, 1, 2], "class_order": classes,
                "risk_boundaries": boundaries,
                "risk_boundary_rule": "Low <= first; Medium <= second; otherwise High",
                "risk_boundary_source": "final-fit training rows only",
                "training": info["training"], "selected_parameters": info["selected_parameters"],
                "selection_validation": fit["selection"]["risk"], "dependencies": fit["dependencies"],
                "source_final_fit_manifest_sha256": sha256(fit_path),
                "source_model_sha256": sha256(source), "package_model_sha256": sha256(packaged),
                "inference_contract_sha256": sha256(contract_path),
                "phase9_3_validation_sha256": sha256(validation_path),
                "fixture_input_sha256": sha256(output / "fixture_input.json"),
                "fixture_expected_sha256": sha256(output / "fixture_expected.json"),
                "evaluation_reference": "Phase 7 outer-fold development reports and Phase 9.2b comparisons; no untouched post-fit test",
                "limitations": ["Market-only research model", "No Shariah result", "Source-quality and historical provenance limits remain disclosed"]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_risk_package(output: Path) -> dict:
    """Check the model and cutoff ties in a fresh Python process."""
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, key in (("risk_model.joblib", "package_model_sha256"),
                      ("fixture_input.json", "fixture_input_sha256"),
                      ("fixture_expected.json", "fixture_expected_sha256")):
        if sha256(output / name) != manifest[key]:
            raise ValueError(f"Changed packaged file: {name}")
    fixture = json.loads((output / "fixture_input.json").read_text(encoding="utf-8"))
    expected = json.loads((output / "fixture_expected.json").read_text(encoding="utf-8"))
    if fixture["feature_order"] != manifest["feature_order"] or expected["class_order"] != manifest["class_order"]:
        raise ValueError("Risk fixture order differs from package")
    model = joblib.load(output / "risk_model.joblib")
    actual = _probabilities(model, manifest["feature_order"], fixture["values"])
    classes = classify_realized_volatility(fixture["boundary_test_values"], manifest["risk_boundaries"])
    if (not np.allclose(actual, expected["probabilities"], rtol=0, atol=1e-12)
            or int(np.argmax(actual)) != expected["predicted_class_code"]
            or classes != expected["boundary_class_codes"] or classes != [0, 1, 1, 2]):
        raise ValueError("Fresh-process risk fixture differs")
    return {"model_version": manifest["model_version"], "fixture_ticker": fixture["ticker"],
            "fixture_date": fixture["session_date"], "probabilities": actual,
            "predicted_class": manifest["class_order"][int(np.argmax(actual))],
            "cutoff_tie_classes": classes, "verified": True}
