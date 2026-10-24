"""Verify frozen Phase 4 inputs and score matched, no-fit Phase 5 baselines.

Run: python -m src.model_training.baseline_models --output reports/generated/current/baseline_model_results.json
"""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import confusion_matrix, f1_score, mean_absolute_error

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.chronological_evaluation_protocol import (
    DEFAULT_DATA, _hash_keys, _role, apply_risk_boundaries, build_protocol,
    load_and_audit,
)

DEFAULT_PROTOCOL = Path("reports/generated/current/chronological_evaluation_protocol.json")
FROZEN_DATA_SHA256 = "71bbe3686cdd75ecbfded9130623c134b45636b6b658c45cc8fba3ecba90be7f"
FROZEN_PROTOCOL_SHA256 = "cbd4b373060ab4d693a893a4325d385061f158ab92406017ca6093a4dfee45bd"


def verify_inputs(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL):
    """Fail closed if either frozen input or any reconstructed fold differs."""
    data_path, protocol_path = Path(data_path), Path(protocol_path)
    if sha256(data_path) != FROZEN_DATA_SHA256:
        raise ValueError("Frozen dataset checksum mismatch")
    if sha256(protocol_path) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Frozen protocol checksum mismatch")
    frame, metadata = load_and_audit(data_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if metadata["output_sha256"] != protocol["dataset_sha256"]:
        raise ValueError("Dataset and protocol versions differ")
    # Reconstructing the complete report validates dates, role keys, eligibility,
    # allowlist, purges, peer groups and training-only risk boundaries together.
    if build_protocol(frame, metadata) != protocol:
        raise ValueError("Frozen fold, feature, eligibility or risk-boundary mismatch")
    return frame, metadata, protocol


def fold_roles(frame, fold, task, role="outer"):
    """Return the two rows sets represented by one frozen protocol role."""
    first = fold["outer_first"] if role == "outer" else fold["inner_first"]
    eval_last = fold["outer_last"] if role == "outer" else fold["inner_last"]
    train = _role(frame, sorted(frame.loc[frame.session_date.lt(first), "session_date"].unique()), first, task=task)
    evaluation = _role(frame, sorted(frame.loc[frame.session_date.between(first, eval_last), "session_date"].unique()),
                       None, fold["outer_first"] if role == "inner" else None, task)
    saved = fold["tasks"][task][role]
    for name, rows in (("train", train), ("evaluation", evaluation)):
        if len(rows) != saved[name + "_rows"] or _hash_keys(rows) != saved[name + "_keys_sha256"]:
            raise ValueError(f"Fold {fold['fold']} {task} {role} {name} row mismatch")
    return train, evaluation


def matched_feature_sets(train, evaluation, protocol):
    """Select cumulative frozen groups on the same eligible fold rows."""
    groups = protocol["experiment_protocol"]["feature_groups"]
    if list(groups) != ["momentum_volatility", "trend_downside", "market_relative", "volume"]:
        raise ValueError("Frozen feature group order mismatch")
    allowlist = protocol["feature_allowlist"]
    columns = []
    matrices = {}
    for name, additions in groups.items():
        if not additions or len(set(additions)) != len(additions) or set(additions) & set(columns):
            raise ValueError("Duplicate or empty frozen feature group")
        columns.extend(additions)
        if set(columns) - set(allowlist):
            raise ValueError("Non-allowlisted feature group")
        from src.model_training.chronological_evaluation_protocol import guarded_training_features
        x_train, x_eval = guarded_training_features(train, evaluation, columns)
        if x_train.isna().any().any() or x_eval.isna().any().any():
            raise ValueError("Missing matched feature value")
        matrices[name] = (x_train, x_eval)
    return matrices


def _classification(y, prediction):
    return {
        "macro_f1": float(f1_score(y, prediction, labels=[0, 1, 2], average="macro", zero_division=0)),
        "ordinal_mae": float(mean_absolute_error(y, prediction)),
        "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1, 2]).tolist(),
    }


def _prior_probability_metrics(y, prior):
    """Three-class log loss and summed multiclass Brier score per row."""
    observed = np.eye(3)[np.asarray(y, dtype=int)]
    probabilities = np.broadcast_to(np.asarray(prior), observed.shape)
    return {"log_loss": float(-np.mean(np.log(np.maximum(probabilities[np.arange(len(y)), y], 1e-15)))),
            "multiclass_brier": float(np.mean(np.sum((probabilities - observed) ** 2, axis=1)))}


def _return_ranking(evaluation, scores):
    """Use each date's same eligible peers; a constant prior has undefined IC."""
    ranked = evaluation[["session_date", "ticker", "return_next_20d"]].copy()
    ranked["score"] = np.asarray(scores)
    daily = []
    for date, group in ranked.groupby("session_date", sort=True):
        has_order = group.score.nunique() > 1
        ordered = group.sort_values(["score", "ticker"], ascending=[False, True], kind="stable")
        correlation = None if not has_order or group.return_next_20d.nunique() < 2 else float(
            spearmanr(group.score, group.return_next_20d).statistic)
        daily.append({"date": date, "peers": len(group), "spearman": correlation,
                      "top10_forward_return": float(ordered.head(10).return_next_20d.mean()) if has_order else None,
                      "universe_forward_return": float(group.return_next_20d.mean())})
    defined = [day["spearman"] for day in daily if day["spearman"] is not None]
    top10 = [day["top10_forward_return"] - day["universe_forward_return"] for day in daily
             if day["top10_forward_return"] is not None]
    return {"dates": len(daily), "defined_spearman_dates": len(defined),
            "mean_daily_spearman": float(np.mean(defined)) if defined else None,
            "mean_top10_minus_universe": float(np.mean(top10)) if top10 else None,
            "daily": daily}


def score_baselines(frame, protocol):
    results = []
    for fold in protocol["folds"]:
        for role, task in ((role, task) for role in ("inner", "outer") for task in ("return", "risk")):
            train, evaluation = fold_roles(frame, fold, task, role)
            if task == "return":
                train_labels = train.relative_return_class.astype(int).to_numpy()
                truth = evaluation.relative_return_class.astype(int).to_numpy()
            else:
                boundaries = fold["tasks"]["risk"][role]["risk_boundaries"]
                train_labels = apply_risk_boundaries(train.risk_volatility_next_20d, boundaries)
                truth = apply_risk_boundaries(evaluation.risk_volatility_next_20d, boundaries)
            counts = np.bincount(train_labels, minlength=3)
            prior = counts / counts.sum()
            prior_class = int(np.argmax(counts))  # deterministic tie rule
            row = {"fold": fold["fold"], "role": role, "task": task,
                   "train_rows": len(train), "evaluation_rows": len(evaluation),
                   "train_keys_sha256": _hash_keys(train), "evaluation_keys_sha256": _hash_keys(evaluation),
                   "train_class_counts": counts.tolist(), "training_class_prior": prior.tolist(),
                   "prior_predicted_class": prior_class,
                   "prior_classification": _classification(truth, np.full(len(truth), prior_class)),
                   "prior_probability_metrics": _prior_probability_metrics(truth, prior),
                   "evaluation_first": fold[role + "_first"],
                   "evaluation_last": fold[role + "_last"]}
            if task == "return":
                row["prior_ranking"] = _return_ranking(evaluation, np.full(len(evaluation), prior[2] - prior[0]))
                row["momentum_20d_ranking"] = _return_ranking(evaluation, evaluation.momentum_20d)
            else:
                trailing = apply_risk_boundaries(evaluation.volatility_20d, boundaries)
                row["risk_boundaries"] = boundaries
                row["trailing_volatility_classification"] = _classification(truth, trailing)
                row["trailing_high_to_low"] = int(((truth == 2) & (trailing == 0)).sum())
                row["prior_high_to_low"] = int(((truth == 2) & (prior_class == 0)).sum())
            results.append(row)
    return results


def run(data_path=DEFAULT_DATA, protocol_path=DEFAULT_PROTOCOL, output=None):
    frame, metadata, protocol = verify_inputs(data_path, protocol_path)
    report = {"stage": "phase5_steps_5_1_5_2", "dataset_sha256": sha256(data_path),
              "dataset_metadata_sha256": sha256(Path(data_path).parent / "dataset_metadata.json"),
              "protocol_sha256": sha256(protocol_path), "protocol_code_sha256": protocol["code_sha256"],
              "baseline_code_sha256": sha256(__file__),
              "feature_allowlist": protocol["feature_allowlist"], "test_start": protocol["test_start"],
              "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                              "numpy": np.__version__},
              "interpretation": "Forward close-to-close returns are research selection diagnostics, not executable trades.",
              "folds": score_baselines(frame, protocol)}
    if output is not None:
        output = Path(output)
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.data, args.protocol, args.output)
    print(json.dumps({"output": str(args.output), "fold_task_results": len(report["folds"])}))
