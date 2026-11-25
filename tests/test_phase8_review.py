import json
from pathlib import Path

import pytest

from src.model_training.phase8.review import build_review_payload


def _phase7_summary():
    return {
        "status": "complete",
        "tasks": {
            "return": {"selection": {"kind": "simple_benchmark", "benchmark": "momentum_20d"}},
            "risk": {
                "selection": {
                    "kind": "simple_benchmark",
                    "benchmark": "volatility_20d_with_fold_training_cutoffs",
                }
            },
        },
    }


def _return_report():
    return {
        "folds": [
            {"benchmark": {"mean_daily_spearman": value, "mean_top10_minus_universe": value / 10}}
            for value in (-0.03, 0.01, -0.01, 0.03)
        ]
    }


def _risk_report():
    return {
        "folds": [
            {
                "benchmark": {
                    "macro_f1": value,
                    "high_recall": 0.6,
                    "ordinal_mae": 0.5,
                    "confusion_matrix": [[2, 1, 0], [1, 2, 1], [1, 1, 3]],
                }
            }
            for value in (0.50, 0.52, 0.54, 0.56)
        ]
    }


def _phase8_result():
    return {
        "status": "complete",
        "model_fitting_performed": False,
        "selection_reopened": False,
        "return": {
            "mean_daily_spearman": 0.02,
            "mean_top10_minus_universe_return": 0.01,
        },
        "risk": {
            "macro_f1": 0.55,
            "high_recall": 0.7,
            "ordinal_mae": 0.4,
            "high_to_low_count": 2,
            "high_outcomes": 20,
            "high_to_low_rate": 0.1,
            "per_class": {"Low": {"recall": 0.4}},
        },
        "limitations": ["Synthetic limitation."],
    }


def test_review_is_descriptive_and_does_not_reopen_selection():
    payload = build_review_payload(
        _phase7_summary(),
        _return_report(),
        _risk_report(),
        _phase8_result(),
        {"example": {"sha256": "abc"}},
        {"comparison_rules": ["No tuning."]},
    )

    assert payload["status"] == "complete"
    assert payload["model_fitting_performed"] is False
    assert payload["selection_reopened"] is False
    assert payload["post_hoc_threshold_created"] is False
    assert payload["return_review"]["development_mean_daily_spearman"] == pytest.approx(0.0)
    assert payload["risk_review"]["development_mean_macro_f1"] == pytest.approx(0.53)
    assert payload["risk_review"]["development_aggregate_high_to_low_rate"] == pytest.approx(0.2)
    assert payload["conclusion"]["procedure_decision"] == "retain_frozen_simple_benchmarks_without_tuning"


def test_colab_notebook_uploads_one_bundle_and_downloads_results_last():
    path = Path("notebooks/phase8_step_8_7_review.ipynb")
    notebook = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    source = "\n".join("".join(cell["source"]) for cell in notebook["cells"])
    final_source = "".join(code_cells[-1]["source"])

    assert "/content/HalalifyAI" in source
    assert "files.upload()" in source
    assert "phase8_step_8_7_inputs.zip" in source
    assert "run_step_8_7_review" in source
    assert "files.download" in final_source
    assert "phase8_step_8_7_results.zip" in final_source
    assert "D:\\" not in source
    assert all(cell["execution_count"] is None for cell in code_cells)
