"""Build the frozen Phase 8 reserved-period features and labels.

Student-run command:
    python -m src.model_training.phase8.build_reserved_dataset

This module materializes outcomes but never evaluates or summarizes benchmark
performance. It refuses to overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import exchange_calendars as xc
import numpy as np
import pandas as pd

from src.feature_engineering.build_feature_dataset import prepare_prices
from src.feature_engineering.market_features import FEATURE_COLUMNS, build_market_features
from src.model_training.chronological_evaluation_protocol import apply_risk_boundaries
from src.model_training.phase8.contract import DEFAULT_CONTRACT, validate_contract


DEFAULT_OUTPUT = Path(
    "data/processed/phase8_model_inputs/phase8_reserved_evaluation_v1"
)
OUTPUT_CSV = "reserved_features_and_labels.csv"
KEYS = ["ticker", "session_date"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def engineer_features(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Apply the frozen 14-feature implementation to company rows and SPY."""
    companies, spy, sessions = prepare_prices(prices)
    benchmark = spy.reset_index().rename(columns={"index": "session_date"})
    combined = pd.concat([companies, benchmark], ignore_index=True)
    features = build_market_features(combined).iloc[: len(companies)].reset_index(drop=True)
    for column in FEATURE_COLUMNS:
        companies[column] = features[column]
    companies["features_complete"] = companies[FEATURE_COLUMNS].notna().all(axis=1)
    return companies, sessions


def add_forward_outcomes(
    frame: pd.DataFrame, sessions: pd.DatetimeIndex
) -> pd.DataFrame:
    """Create only the frozen next-20-session continuous outcomes."""
    out = frame.copy()
    dates = pd.to_datetime(out["session_date"], format="%Y-%m-%d", errors="raise")
    ends = pd.Series(sessions, index=sessions).shift(-20)
    out["target_window_end"] = dates.map(ends).dt.strftime("%Y-%m-%d")
    out["return_next_20d"] = np.nan
    out["risk_volatility_next_20d"] = np.nan
    for _, group in out.groupby("ticker", sort=True):
        index = pd.DatetimeIndex(pd.to_datetime(group["session_date"]))
        close = pd.Series(group["adjusted_close"].to_numpy(), index=index).reindex(sessions)
        daily_return = close.pct_change(fill_method=None)
        future_risk = (
            daily_return.rolling(20, min_periods=20).std(ddof=1).shift(-20)
            * np.sqrt(252)
        )
        future_return = (close.shift(-20) / close - 1).where(future_risk.notna())
        out.loc[group.index, "return_next_20d"] = future_return.reindex(index).to_numpy()
        out.loc[group.index, "risk_volatility_next_20d"] = future_risk.reindex(index).to_numpy()
    return out


def apply_frozen_labels(
    frame: pd.DataFrame, low_cutoff: float, medium_cutoff: float
) -> pd.DataFrame:
    """Apply the frozen return-peer and training-cutoff risk label rules."""
    out = frame.copy()
    features_complete = out[FEATURE_COLUMNS].notna().all(axis=1)

    return_candidate = out["volume"].gt(0) & out["return_next_20d"].notna()
    return_values = out["return_next_20d"].where(return_candidate)
    outcome_count = return_values.groupby(out["session_date"]).transform("count")
    outcome_rank = return_values.groupby(out["session_date"]).rank(method="average")
    return_available = (
        return_candidate
        & features_complete
        & out["active_peer_count"].ge(45)
        & outcome_count.ge(45)
    )
    out["outcome_peer_count"] = outcome_count.astype("Int64")
    out["relative_return_class"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[return_available, "relative_return_class"] = np.select(
        [
            outcome_rank[return_available].le(outcome_count[return_available] / 3),
            outcome_rank[return_available].le(2 * outcome_count[return_available] / 3),
        ],
        [0, 1],
        default=2,
    )
    out["return_eligibility_reason"] = np.select(
        [
            ~features_complete,
            out["volume"].le(0),
            out["return_next_20d"].isna(),
            out["active_peer_count"].lt(45),
            outcome_count.lt(45),
        ],
        [
            "feature_warmup_or_missing",
            "inactive",
            "missing_label",
            "activity_quorum",
            "outcome_quorum",
        ],
        default="eligible",
    )
    out["return_eligible"] = out["return_eligibility_reason"].eq("eligible")

    risk_available = features_complete & out["risk_volatility_next_20d"].notna()
    out["risk_class"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[risk_available, "risk_class"] = apply_risk_boundaries(
        out.loc[risk_available, "risk_volatility_next_20d"],
        [low_cutoff, medium_cutoff],
    )
    out["risk_eligibility_reason"] = np.select(
        [~features_complete, out["risk_volatility_next_20d"].isna()],
        ["feature_warmup_or_missing", "missing_label"],
        default="eligible",
    )
    out["risk_eligible"] = out["risk_eligibility_reason"].eq("eligible")
    return out


def validate_reserved_rows(
    frame: pd.DataFrame, contract: dict[str, Any], expected_sessions: pd.DatetimeIndex
) -> dict[str, Any]:
    chronology = contract["chronology"]
    evaluation = frame.loc[
        frame["session_date"].between(
            chronology["reserved_evaluation_start"],
            chronology["reserved_evaluation_end"],
        )
    ].copy()
    if evaluation.empty or evaluation.duplicated(KEYS).any():
        raise ValueError("Reserved evaluation rows are empty or duplicated")
    if evaluation["ticker"].nunique() != 50 or evaluation["ticker"].eq("SPY").any():
        raise ValueError("Reserved evaluation does not contain the frozen 50 companies")
    dates = sorted(evaluation["session_date"].unique())
    expected = expected_sessions.strftime("%Y-%m-%d").tolist()
    if dates != expected or len(dates) != 187:
        raise ValueError("Reserved evaluation sessions differ from the contract")
    if len(evaluation) != 50 * 187:
        raise ValueError("Reserved evaluation does not contain one row per company/session")
    if evaluation[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("A reserved row has a missing frozen base feature")
    if evaluation[["target_window_end", "return_next_20d", "risk_volatility_next_20d"]].isna().any().any():
        raise ValueError("A reserved row has an incomplete future outcome")
    if evaluation["target_window_end"].gt(chronology["twentieth_support_session"]).any():
        raise ValueError("A reserved target exceeds the frozen support window")
    for task in ("return", "risk"):
        if not evaluation[f"{task}_eligible"].all():
            raise ValueError(f"Not every reserved row is {task}-eligible")
    minimum_active = int(evaluation.groupby("session_date")["active_peer_count"].first().min())
    if minimum_active < 45:
        raise ValueError("Reserved evaluation active-company quorum failed")
    return {
        "rows": int(len(evaluation)),
        "companies": int(evaluation["ticker"].nunique()),
        "sessions": int(len(dates)),
        "first_session": dates[0],
        "last_session": dates[-1],
        "last_target_window_end": evaluation["target_window_end"].max(),
        "return_eligible_rows": int(evaluation["return_eligible"].sum()),
        "risk_eligible_rows": int(evaluation["risk_eligible"].sum()),
        "minimum_active_companies": minimum_active,
    }


def build(
    *,
    root: Path,
    contract_path: Path,
    output_dir: Path,
) -> Path:
    root = root.resolve()
    contract_path = (
        (root / contract_path).resolve() if not contract_path.is_absolute() else contract_path
    )
    output_dir = (root / output_dir).resolve() if not output_dir.is_absolute() else output_dir
    if output_dir.exists():
        raise FileExistsError(output_dir)

    contract_validation = validate_contract(contract_path, root)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    prices_identity = contract["input_identities"]["accepted_cleaned_csv"]
    prices_path = root / prices_identity["path"]
    if sha256(prices_path) != prices_identity["sha256"]:
        raise ValueError("Accepted Phase 8 clean prices differ from the contract")

    prices = pd.read_csv(prices_path, low_memory=False)
    featured, sessions = engineer_features(prices)
    labeled = apply_frozen_labels(
        add_forward_outcomes(featured, sessions),
        contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
        contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
    )
    chronology = contract["chronology"]
    calendar = xc.get_calendar(
        "XNYS",
        start=pd.Timestamp(chronology["reserved_evaluation_start"]) - pd.Timedelta(days=10),
        end=pd.Timestamp(chronology["reserved_evaluation_end"]) + pd.Timedelta(days=10),
    )
    expected_sessions = calendar.sessions_in_range(
        chronology["reserved_evaluation_start"], chronology["reserved_evaluation_end"]
    ).tz_localize(None)
    validation = validate_reserved_rows(labeled, contract, expected_sessions)
    reserved = labeled.loc[
        labeled["session_date"].between(
            chronology["reserved_evaluation_start"], chronology["reserved_evaluation_end"]
        )
    ].copy()
    reserved["dataset_role"] = "reserved_evaluation"
    reserved = reserved.sort_values(KEYS, kind="stable").reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=False)
    destination = output_dir / OUTPUT_CSV
    reserved.to_csv(destination, index=False)
    metadata = {
        "schema_version": 1,
        "stage": "phase_8_step_8_3_reserved_dataset",
        "status": "validated_not_scored",
        "contract": contract_path.relative_to(root).as_posix(),
        "contract_sha256": contract_validation["contract_sha256"],
        "source_cleaned_csv": prices_identity["path"],
        "source_cleaned_sha256": prices_identity["sha256"],
        "output_csv": OUTPUT_CSV,
        "output_sha256": sha256(destination),
        "feature_columns": FEATURE_COLUMNS,
        "scoring_allowlist": contract["feature_contract"]["scoring_allowlist"],
        "risk_cutoffs": [
            contract["label_contract"]["risk_classes"]["low_upper_inclusive"],
            contract["label_contract"]["risk_classes"]["medium_upper_inclusive"],
        ],
        "validation": validation,
        "outcomes_materialized": True,
        "outcomes_scored": False,
        "performance_metrics_calculated": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": {
            "src/model_training/phase8/build_reserved_dataset.py": sha256(Path(__file__)),
            "src/model_training/phase8/contract.py": sha256(
                root / "src/model_training/phase8/contract.py"
            ),
            "src/feature_engineering/market_features.py": sha256(
                root / "src/feature_engineering/market_features.py"
            ),
        },
        "limitations": [
            "The fixed 50-stock universe retains survivorship and selection bias.",
            "Provider all-adjusted prices include documented as-of drift in the overlap.",
            "Corporate-action magnitudes remain independently unverified.",
            "This dataset is not portfolio, trading, or Shariah-screening evidence.",
        ],
    }
    write_json(output_dir / "dataset_metadata.json", metadata)
    write_json(
        output_dir / "validation_report.json",
        {
            "stage": "phase_8_step_8_3_dataset_validation",
            "passed": True,
            "outcomes_materialized": True,
            "outcomes_scored": False,
            "performance_metrics_calculated": False,
            "contract_sha256": contract_validation["contract_sha256"],
            **validation,
            "dataset_sha256": metadata["output_sha256"],
        },
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()
    destination = build(root=args.root, contract_path=args.contract, output_dir=args.output_dir)
    print(f"Validated reserved dataset written to {destination}")


if __name__ == "__main__":
    main()
