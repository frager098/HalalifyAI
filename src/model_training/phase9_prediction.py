"""Research-only after-close inference from the two frozen Phase 9 packages."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.model_training.phase9_feature_inference import reconstruct_phase9_features
from src.model_training.phase9_return_package import sha256


RETURN_PACKAGE = Path("reports/model_evaluation/phase9_return_package_v1")
RISK_PACKAGE = Path("reports/model_evaluation/phase9_risk_package_v1")


def _load_package(root: Path, task: str):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    model_path = root / f"{task}_model.joblib"
    if sha256(model_path) != manifest["package_model_sha256"]:
        raise ValueError(f"Changed {task} model artifact")
    if manifest["evidence_status"] != "development_only" or manifest["class_codes"] != [0, 1, 2]:
        raise ValueError(f"Unsupported {task} package metadata")
    model = joblib.load(model_path)
    fitted_classes = model[-1].classes_ if task == "return" else model.classes_
    if not np.array_equal(fitted_classes, [0, 1, 2]):
        raise ValueError(f"Unexpected {task} estimator class order")
    return manifest, model


def _checked_probabilities(model, rows: pd.DataFrame, features: list[str], task: str) -> np.ndarray:
    values = rows[features]
    if len(features) == 0 or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError(f"Missing or nonfinite {task} features")
    probabilities = model.predict_proba(values)
    if (probabilities.shape != (len(rows), 3) or not np.isfinite(probabilities).all()
            or not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-12)
            or (probabilities < 0).any() or (probabilities > 1).any()):
        raise ValueError(f"Invalid {task} probabilities")
    return probabilities


def predict_phase9(
    bars: pd.DataFrame,
    decision_date: str,
    expected_tickers: set[str],
    return_package: Path = RETURN_PACKAGE,
    risk_package: Path = RISK_PACKAGE,
) -> dict:
    """Predict all active peers; rank by return score with ticker tie-break."""
    features = reconstruct_phase9_features(bars, decision_date, expected_tickers)
    return_info, return_model = _load_package(Path(return_package), "return")
    risk_info, risk_model = _load_package(Path(risk_package), "risk")
    ret = _checked_probabilities(return_model, features, return_info["feature_order"], "return")
    risk = _checked_probabilities(risk_model, features, risk_info["feature_order"], "risk")
    if return_info["class_order"] != ["Lower", "Middle", "Higher"] or risk_info["class_order"] != ["Low", "Medium", "High"]:
        raise ValueError("Unexpected package class names")
    records = []
    for index, ticker in enumerate(features.ticker):
        return_code = int(np.argmax(ret[index]))
        risk_code = int(np.argmax(risk[index]))
        records.append({
            "ticker": ticker,
            "return_class": return_info["class_order"][return_code],
            "return_probabilities": {name: float(ret[index, code]) for code, name in enumerate(return_info["class_order"])},
            "return_rank_score": float(ret[index, 2] - ret[index, 0]),
            "risk_class": risk_info["class_order"][risk_code],
            "risk_probabilities": {name: float(risk[index, code]) for code, name in enumerate(risk_info["class_order"])},
        })
    records.sort(key=lambda row: (-row["return_rank_score"], row["ticker"]))
    for rank, row in enumerate(records, start=1):
        row["return_rank"] = rank
    return {
        "session_date": decision_date,
        "decision_time": "after_close",
        "horizon_trading_sessions": 20,
        "evidence_status": "development_only",
        "return_model_version": return_info["model_version"],
        "risk_model_version": risk_info["model_version"],
        "predictions": records,
    }
