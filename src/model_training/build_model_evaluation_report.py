"""Build the Phase 5 evaluator tables and figures from frozen research inputs.

Run: python -m src.model_training.build_model_evaluation_report
Existing verified model artifacts are reused; absent artifacts are fitted by
their source modules. Run from the repository root.
"""

import json
import platform
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import sklearn

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.baseline_models import (DEFAULT_DATA, DEFAULT_PROTOCOL,verify_inputs)
from src.model_training.return_logistic_classifier import run as fit_return_logistic
from src.model_training.return_gradient_boosting_classifier import run as fit_return_tree
from src.model_training.risk_logistic_classifier import run as fit_risk_logistic
from src.model_training.risk_gradient_boosting_classifier import run as fit_risk_tree
from src.model_training.evaluate_return_models import review as review_return
from src.model_training.evaluate_risk_models import review as review_risk

OUTPUT = Path("reports/generated/current/model_evaluation_package")
MODEL_DIRS = {
    "return_logistic": Path("reports/generated/current/return_logistic_classifier"),
    "return_tree": Path("reports/generated/current/return_gradient_boosting_classifier"),
    "risk_logistic": Path("reports/generated/current/risk_logistic_classifier"),
    "risk_tree": Path("reports/generated/current/risk_gradient_boosting_classifier"),
}
RUNNERS = {
    "return_logistic": fit_return_logistic,
    "return_tree": fit_return_tree,
    "risk_logistic": fit_risk_logistic,
    "risk_tree": fit_risk_tree,
}


def _ensure_model_artifacts():
    """A fresh checkout can fit; an existing partial artifact fails clearly."""
    for name, directory in MODEL_DIRS.items():
        if directory.exists():
            if not (directory / "report.json").is_file() or not (directory / "outer_predictions.csv").is_file():
                raise ValueError(f"Incomplete {name} artifact: {directory}")
            continue
        RUNNERS[name](output_dir=directory)


def _fold_table(protocol):
    records = []
    for fold in protocol["folds"]:
        return_outer = fold["tasks"]["return"]["outer"]
        risk_outer = fold["tasks"]["risk"]["outer"]
        records.append({"fold": fold["fold"], "inner_first": fold["inner_first"],
                        "inner_last": fold["inner_last"], "outer_first": fold["outer_first"],
                        "outer_last": fold["outer_last"],
                        "return_train_rows": return_outer["train_rows"],
                        "return_eval_rows": return_outer["evaluation_rows"],
                        "risk_train_rows": risk_outer["train_rows"],
                        "risk_eval_rows": risk_outer["evaluation_rows"],
                        "risk_low_cutoff": risk_outer["risk_boundaries"][0],
                        "risk_high_cutoff": risk_outer["risk_boundaries"][1]})
    return pd.DataFrame(records)


def _return_tables(report):
    records = []
    for fold in report["folds"]:
        for name, method in fold["methods"].items():
            ranking = method["ranking"]
            records.append({"fold": fold["fold"], "method": name,
                            "mean_daily_spearman": ranking["mean_daily_spearman"],
                            "mean_top10_minus_universe": ranking.get("mean_top10_minus_universe"),
                            "macro_f1": method.get("classification", {}).get("macro_f1")})
    return pd.DataFrame(records)


def _risk_tables(report):
    fold_records, class_records, confusion_records = [], [], []
    for fold in report["folds"]:
        for name, method in fold["methods"].items():
            classes = method["classification"]
            fold_records.append({"fold": fold["fold"], "method": name,
                                 "macro_f1": classes["macro_f1"],
                                 "high_recall": classes["per_class"]["High"]["recall"],
                                 "high_predicted_low": classes["high_predicted_low_count"],
                                 "ordinal_mae": classes["ordinal_mae"],
                                 "log_loss": method.get("probability", {}).get("log_loss"),
                                 "multiclass_brier": method.get("probability", {}).get("multiclass_brier")})
            for label, values in classes["per_class"].items():
                class_records.append({"fold": fold["fold"], "method": name,
                                      "class": label, **values})
            for i, observed in enumerate(("Low", "Medium", "High")):
                for j, predicted in enumerate(("Low", "Medium", "High")):
                    confusion_records.append({"fold": fold["fold"], "method": name,
                                              "observed": observed, "predicted": predicted,
                                              "count": classes["confusion_matrix"][i][j]})
    return pd.DataFrame(fold_records), pd.DataFrame(class_records), pd.DataFrame(confusion_records)


def _bar_svg(path, title, records, y_label, zero=False):
    """Small deterministic SVG figure, with fold variation visible beside means."""
    methods = list(dict.fromkeys(row["method"] for row in records))
    folds = sorted({row["fold"] for row in records})
    values = [row["value"] for row in records]
    low, high = min(values + ([0] if zero else [])), max(values + ([0] if zero else []))
    margin = max((high - low) * 0.12, 0.01)
    low, high = low - margin, high + margin
    width, height = 940, 430
    left, top, plot_width, plot_height = 88, 72, 800, 270
    palette = ["#315f96", "#bf6735", "#3f8669", "#7665a4"]
    def y(value):
        return top + (high - value) / (high - low) * plot_height
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              f'<text x="{left}" y="31" font-family="Arial" font-size="20" font-weight="bold">{escape(title)}</text>',
              f'<text x="{left}" y="53" font-family="Arial" font-size="12" fill="#555">{escape(y_label)}</text>']
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        value = low + fraction * (high - low)
        yy = y(value)
        pieces.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{left+plot_width}" y2="{yy:.2f}" stroke="#e4e8ed"/>')
        pieces.append(f'<text x="{left-8}" y="{yy+4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{value:.2f}</text>')
    group_width = plot_width / len(folds)
    bar_width = min(36, group_width / (len(methods) + 1))
    baseline = y(0) if zero else y(low)
    for row in records:
        group = folds.index(row["fold"])
        method = methods.index(row["method"])
        x = left + group * group_width + group_width / 2 + (method - (len(methods)-1)/2) * (bar_width + 3) - bar_width/2
        yy = y(row["value"])
        pieces.append(f'<rect x="{x:.2f}" y="{min(yy,baseline):.2f}" width="{bar_width:.2f}" height="{max(abs(yy-baseline),0.5):.2f}" fill="{palette[method]}"/>')
    for index, fold in enumerate(folds):
        x = left + (index + 0.5) * group_width
        pieces.append(f'<text x="{x:.2f}" y="{top+plot_height+22}" text-anchor="middle" font-family="Arial" font-size="12">Fold {fold}</text>')
    for index, method in enumerate(methods):
        x = left + index * 210
        pieces.append(f'<rect x="{x}" y="390" width="14" height="14" fill="{palette[index]}"/>')
        pieces.append(f'<text x="{x+20}" y="402" font-family="Arial" font-size="11">{escape(method)}</text>')
    pieces.append('</svg>')
    path.write_text("\n".join(pieces), encoding="utf-8")


def build_results_package(output_dir=OUTPUT):
    frame, metadata, protocol = verify_inputs()
    _ensure_model_artifacts()
    return_report = review_return()
    risk_report = review_risk()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {"folds.csv": _fold_table(protocol),
              "return_fold_metrics.csv": _return_tables(return_report)}
    risk_folds, risk_classes, risk_confusion = _risk_tables(risk_report)
    tables.update({"risk_fold_metrics.csv": risk_folds,
                   "risk_class_metrics.csv": risk_classes,
                   "risk_confusion_matrices.csv": risk_confusion})
    for name, table in tables.items():
        table.to_csv(output_dir / name, index=False, lineterminator="\n", float_format="%.17g")
    return_rows = tables["return_fold_metrics.csv"]
    _bar_svg(output_dir / "return_fold_spearman.svg", "Return ranking by development fold",
             [{"fold": int(row.fold), "method": row.method, "value": float(row.mean_daily_spearman)}
              for row in return_rows.itertuples() if row.method in
              ("LogisticRegression", "HistGradientBoosting", "momentum_20d")],
             "Mean same-date Spearman; zero indicates no average ordering", zero=True)
    _bar_svg(output_dir / "risk_fold_f1.svg", "Risk class quality by development fold",
             [{"fold": int(row.fold), "method": row.method, "value": float(row.macro_f1)}
              for row in risk_folds.itertuples() if row.method in
              ("LogisticRegression", "HistGradientBoosting", "trailing_volatility_20d")],
             "Macro F1 across Low, Medium and High")
    names = [*tables, "return_fold_spearman.svg", "risk_fold_f1.svg"]
    summary = {"stage": "phase5_evaluator", "dataset_sha256": metadata["output_sha256"],
               "protocol_sha256": sha256(DEFAULT_PROTOCOL), "code_sha256": sha256(__file__),
               "notebook_sha256": sha256("notebooks/model_evaluation_report.ipynb"),
               "model_prediction_sha256": {
                   name: json.loads((directory / "report.json").read_text(encoding="utf-8"))["prediction_sha256"]
                   for name, directory in MODEL_DIRS.items()},
               "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                               "numpy": np.__version__, "scikit_learn": sklearn.__version__},
               "data": {"rows": len(frame), "companies": frame.ticker.nunique(),
                        "sessions": frame.session_date.nunique(),
                        "return_eligible": int(frame.return_eligible.sum()),
                        "risk_eligible": int(frame.risk_eligible.sum()),
                        "reused_test_start": protocol["test_start"]},
               "return_mean_fold_spearman": return_report["mean_fold_spearman"],
               "risk_summary": risk_report["summary"],
               "return_decision": "No return approach selected; momentum remains a comparison baseline with near-zero mean ranking correlation.",
               "risk_status": "Tree is a provisional candidate; small F1 gain and High-risk misses require the Phase 5 conclusion.",
               "limitations": ["Current-stock research universe has survivorship and historical-identity limitations.",
                               "2024-2025 test outcomes were previously viewed and are excluded from model selection.",
                               "Overlapping 20-session outcomes reduce row-wise independence.",
                               "Close-to-close forward returns are research diagnostics, not executable portfolio returns.",
                               "No historical Shariah screen, next-session execution price or transaction costs are applied."],
               "artifacts": {name: sha256(output_dir / name) for name in names}}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    return summary, tables, output_dir


def show_table(table):
    """Display clean tables in Jupyter; retain a plain-Python fallback."""
    try:
        from IPython.display import display
    except ImportError:
        print(table.to_string(index=False))
    else:
        display(table)


def show_svg(path):
    try:
        from IPython.display import SVG, display
    except ImportError:
        print(path)
    else:
        display(SVG(filename=str(path)))


if __name__ == "__main__":
    result, _, location = build_results_package()
    print(json.dumps({"output": str(location), "rows": result["data"]["rows"],
                      "folds": 4, "artifacts": list(result["artifacts"])}))
