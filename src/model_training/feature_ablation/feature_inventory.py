"""Inventory Phase 6 candidate features without fitting a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.feature_engineering.build_feature_dataset import sha256
from src.model_training.feature_ablation.ablation_contract import (
    DEFAULT_DATASET,
    DEFAULT_METADATA,
    DEFAULT_OUTPUT as DEFAULT_CONTRACT,
    EXPECTED_FEATURE_ALLOWLIST,
    ContractMismatchError,
    build_ablation_contract_report,
)
from src.model_training.chronological_evaluation_protocol import (
    build_protocol,
    load_and_audit,
)


DEFAULT_INVENTORY_JSON = Path(
    "reports/model_evaluation/feature_ablation/v1/feature_inventory.json"
)
DEFAULT_INVENTORY_CSV = DEFAULT_INVENTORY_JSON.with_suffix(".csv")

COMMON_AVAILABILITY_RULE = (
    "Calculated after session t closes using only company and benchmark data "
    "from shared exchange sessions at or before t; earliest use is the next "
    "observed session. Missing bars remain missing and break rolling windows."
)

FEATURE_CATALOG = {
    "return_1d": {
        "group": "downside_trend",
        "formula": "adjusted_close(t) / adjusted_close(t-1) - 1",
        "lookback": "1 return interval (2 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "momentum_5d": {
        "group": "momentum",
        "formula": "adjusted_close(t) / adjusted_close(t-5) - 1",
        "lookback": "5 return intervals (6 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "momentum_20d": {
        "group": "momentum",
        "formula": "adjusted_close(t) / adjusted_close(t-20) - 1",
        "lookback": "20 return intervals (21 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "momentum_60d": {
        "group": "momentum",
        "formula": "adjusted_close(t) / adjusted_close(t-60) - 1",
        "lookback": "60 return intervals (61 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "volatility_20d": {
        "group": "volatility",
        "formula": "sample_std(return_1d[t-19:t]) * sqrt(252)",
        "lookback": "20 daily returns (21 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "volatility_60d": {
        "group": "volatility",
        "formula": "sample_std(return_1d[t-59:t]) * sqrt(252)",
        "lookback": "60 daily returns (61 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "downside_dev_20d": {
        "group": "downside_trend",
        "formula": "sqrt(mean(min(return_1d, 0)^2 over 20 returns)) * sqrt(252)",
        "lookback": "20 daily returns (21 adjusted closes)",
        "source_inputs": ["adjusted_close"],
    },
    "drawdown_from_peak_60d": {
        "group": "downside_trend",
        "formula": "adjusted_close(t) / max(adjusted_close[t-59:t]) - 1",
        "lookback": "60 adjusted closes including t",
        "source_inputs": ["adjusted_close"],
    },
    "price_to_sma20": {
        "group": "downside_trend",
        "formula": "adjusted_close(t) / mean(adjusted_close[t-19:t]) - 1",
        "lookback": "20 adjusted closes including t",
        "source_inputs": ["adjusted_close"],
    },
    "price_to_sma50": {
        "group": "downside_trend",
        "formula": "adjusted_close(t) / mean(adjusted_close[t-49:t]) - 1",
        "lookback": "50 adjusted closes including t",
        "source_inputs": ["adjusted_close"],
    },
    "volume_ratio_20d": {
        "group": "volume",
        "formula": "volume(t) / mean(volume[t-19:t])",
        "lookback": "20 company-volume observations including t",
        "source_inputs": ["volume"],
    },
    "spy_momentum_20d": {
        "group": "market_relative",
        "formula": "product(1 + SPY_return[t-19:t]) - 1",
        "lookback": "20 same-session SPY returns",
        "source_inputs": ["spy_return"],
    },
    "excess_momentum_20d": {
        "group": "market_relative",
        "formula": "momentum_20d - spy_momentum_20d",
        "lookback": "20 return intervals for company and SPY",
        "source_inputs": ["adjusted_close", "spy_return"],
    },
    "market_beta_60d": {
        "group": "market_relative",
        "formula": "cov(company_return, SPY_return, 60) / var(SPY_return, 60)",
        "lookback": "60 paired company and SPY daily returns",
        "source_inputs": ["adjusted_close", "spy_return"],
    },
}

EXPECTED_AVAILABILITY = {
    "return_1d": ("2016-01-05", 50),
    "momentum_5d": ("2016-01-11", 250),
    "momentum_20d": ("2016-02-02", 1000),
    "momentum_60d": ("2016-03-31", 3000),
    "volatility_20d": ("2016-02-02", 1000),
    "volatility_60d": ("2016-03-31", 3000),
    "downside_dev_20d": ("2016-02-02", 1000),
    "drawdown_from_peak_60d": ("2016-03-30", 2950),
    "price_to_sma20": ("2016-02-01", 950),
    "price_to_sma50": ("2016-03-15", 2450),
    "volume_ratio_20d": ("2016-02-01", 950),
    "spy_momentum_20d": ("2016-02-02", 980),
    "excess_momentum_20d": ("2016-02-02", 1000),
    "market_beta_60d": ("2016-03-31", 3000),
}

EXCLUDED_COLUMNS = {
    "ticker": ("identifier", "Row key used for grouping; not a numerical predictor."),
    "session_date": ("identifier", "Decision-time key used for chronology; not a predictor."),
    "open": ("raw_market_input", "Raw price level is excluded; approved stationary features use adjusted close."),
    "high": ("raw_market_input", "Raw price level is excluded from the frozen allowlist."),
    "low": ("raw_market_input", "Raw price level is excluded from the frozen allowlist."),
    "close": ("raw_market_input", "Unadjusted raw price level is excluded."),
    "volume": ("raw_market_input", "Raw scale is excluded; only trailing volume_ratio_20d is approved."),
    "adjusted_close": ("raw_market_input", "Raw price level is an input to stationary features, not a predictor."),
    "dataset_version": ("provenance", "Dataset provenance must not enter model fitting."),
    "instrument_id": ("identifier", "Provider identifier can encode issuer identity and is not approved."),
    "security_type": ("provenance", "Source metadata is not an approved predictor."),
    "currency": ("provenance", "The initial universe is USD U.S. equities; this source field is not approved."),
    "dividend_per_share": ("unavailable_source", "Missing in every row and not validated as a point-in-time feature."),
    "split_ratio": ("unavailable_source", "Missing in every row and retained only as a source limitation."),
    "bar_available_at": ("unavailable_source", "Missing in every row; availability is bounded to after session close."),
    "adjustment_verified": ("quality_flag", "Audit state is not a financial predictor."),
    "data_quality_flags": ("quality_flag", "Audit metadata must not become a learned signal."),
    "source_row": ("provenance", "Provider-row provenance must not enter fitting."),
    "split_close_return": ("quality_diagnostic", "Corporate-action comparison diagnostic, not an approved feature."),
    "provider_all_adjusted_return": ("quality_diagnostic", "Adjustment diagnostic, not an approved feature."),
    "adjustment_factor": ("quality_diagnostic", "Adjustment diagnostic, not an approved feature."),
    "large_return_review": ("quality_flag", "Manual-review flag must not become a model signal."),
    "zero_volume_review": ("quality_flag", "Data-review flag must not become a model signal."),
    "identity_history_verified": ("quality_flag", "Historical-identity audit state is not a predictor."),
    "core_ready": ("quality_flag", "Pipeline readiness flag is not a market feature."),
    "spy_return": ("raw_market_input", "Same-session source for approved market-relative rolling features only."),
    "active_peer_count": ("eligibility", "Universe-coverage check used for eligibility, not prediction."),
    "activity_quorum_met": ("eligibility", "Eligibility flag must not enter the feature matrix."),
    "nominal_split": ("split", "Split membership would leak evaluation design."),
    "features_complete": ("eligibility", "Missingness-derived pipeline flag is used only for filtering."),
    "target_window_end": ("future_target", "Contains the end date of the future outcome window."),
    "return_next_20d": ("future_target", "Future return outcome is a target, never a predictor."),
    "risk_volatility_next_20d": ("future_target", "Future realized risk is a target, never a predictor."),
    "outcome_peer_count": ("future_target", "Count depends on future-outcome availability."),
    "relative_return_class": ("target_label", "Return label is the prediction target."),
    "return_label_reason": ("target_label", "Reason depends on future-label availability."),
    "dataset_split": ("split", "Purged split membership would leak evaluation design."),
    "risk_class": ("target_label", "Saved global risk label is a target and is refit inside folds."),
    "return_eligibility_reason": ("eligibility", "Task filtering field can depend on label availability."),
    "return_eligible": ("eligibility", "Task filtering flag is not a predictor."),
    "risk_eligibility_reason": ("eligibility", "Task filtering field can depend on label availability."),
    "risk_eligible": ("eligibility", "Task filtering flag is not a predictor."),
}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ContractMismatchError(f"Missing {label}: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractMismatchError(f"{label} must contain a JSON object")
    return value


def _verified_recovery_inputs(
    dataset_path: Path,
    metadata_path: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    """Verify a rebuilt Phase 3/4 input set before inventorying features.

    This path exists for a lost generated-evidence package.  It does not
    replace the original frozen Phase 5 experiment: it proves only that the
    supplied dataset and saved chronological protocol reproduce each other.
    Phase 6.2 inventories inputs and does not fit or select a model.
    """

    dataset_path, metadata_path, protocol_path = map(
        Path, (dataset_path, metadata_path, protocol_path)
    )
    if metadata_path.resolve() != dataset_path.with_name(
        "dataset_metadata.json"
    ).resolve():
        raise ContractMismatchError(
            "Recovery metadata must be dataset_metadata.json beside the dataset"
        )
    metadata = _load_json(metadata_path, "recovery dataset metadata")
    if sha256(dataset_path) != metadata.get("output_sha256"):
        raise ContractMismatchError(
            "Recovery dataset checksum differs from its dataset_metadata.json"
        )
    saved_protocol = _load_json(protocol_path, "recovery chronological protocol")
    if saved_protocol.get("dataset_sha256") != sha256(dataset_path):
        raise ContractMismatchError(
            "Recovery protocol was created for a different dataset"
        )
    frame, audited_metadata = load_and_audit(dataset_path)
    if audited_metadata != metadata:
        raise ContractMismatchError(
            "Recovery dataset metadata changes during the Phase 4 audit"
        )
    if build_protocol(frame, metadata) != saved_protocol:
        raise ContractMismatchError(
            "Recovery protocol does not reproduce from the supplied dataset"
        )
    return {
        "dataset": {"path": str(dataset_path), "sha256": sha256(dataset_path)},
        "metadata": {"path": str(metadata_path), "sha256": sha256(metadata_path)},
        "chronological_protocol": {
            "path": str(protocol_path),
            "sha256": sha256(protocol_path),
        },
    }


def _build_inventory(
    dataset_path: Path,
    metadata_path: Path,
    input_identities: dict[str, Any],
    evidence_mode: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Classify every frozen dataset column and describe valid candidates."""

    metadata = _load_json(metadata_path, "dataset metadata")
    header = pd.read_csv(dataset_path, nrows=0).columns.tolist()
    expected_columns = set(FEATURE_CATALOG) | set(EXCLUDED_COLUMNS)
    if set(header) != expected_columns or len(header) != len(expected_columns):
        missing = sorted(expected_columns - set(header))
        unclassified = sorted(set(header) - expected_columns)
        raise ContractMismatchError(
            f"Dataset column inventory mismatch; missing={missing}, unclassified={unclassified}"
        )
    if list(FEATURE_CATALOG) != EXPECTED_FEATURE_ALLOWLIST:
        raise ContractMismatchError("Feature catalog differs from the frozen allowlist")
    if set(metadata["missingness"]) != set(header):
        raise ContractMismatchError("Metadata missingness does not cover every dataset column")

    values = pd.read_csv(dataset_path, usecols=["session_date", *FEATURE_CATALOG])
    rows: list[dict[str, Any]] = []
    for feature, definition in FEATURE_CATALOG.items():
        available = values[feature].notna()
        first = values.loc[available, "session_date"].min()
        last = values.loc[available, "session_date"].max()
        missing = int((~available).sum())
        expected_first, expected_missing = EXPECTED_AVAILABILITY[feature]
        if first != expected_first or missing != expected_missing:
            raise ContractMismatchError(
                f"{feature} availability mismatch: first={first}, missing={missing}"
            )
        if missing != metadata["missingness"][feature]:
            raise ContractMismatchError(f"{feature} missingness differs from metadata")
        rows.append(
            {
                "column": feature,
                "status": "approved_market_candidate",
                "group": definition["group"],
                "formula": definition["formula"],
                "lookback": definition["lookback"],
                "source_inputs": ", ".join(definition["source_inputs"]),
                "earliest_usable_date": first,
                "latest_available_date": last,
                "missing_rows": missing,
                "missing_percent": round(100 * missing / len(values), 6),
                "information_availability_rule": COMMON_AVAILABILITY_RULE,
                "exclusion_reason": "",
            }
        )

    for column in header:
        if column in FEATURE_CATALOG:
            continue
        category, reason = EXCLUDED_COLUMNS[column]
        rows.append(
            {
                "column": column,
                "status": "excluded",
                "group": category,
                "formula": "",
                "lookback": "",
                "source_inputs": "",
                "earliest_usable_date": "",
                "latest_available_date": "",
                "missing_rows": int(metadata["missingness"][column]),
                "missing_percent": round(
                    100 * metadata["missingness"][column] / metadata["rows"], 6
                ),
                "information_availability_rule": "Not eligible as a model input.",
                "exclusion_reason": reason,
            }
        )

    inventory = pd.DataFrame(rows)
    groups = {
        name: inventory.loc[
            (inventory["status"] == "approved_market_candidate")
            & (inventory["group"] == name),
            "column",
        ].tolist()
        for name in (
            "momentum",
            "volatility",
            "downside_trend",
            "market_relative",
            "volume",
        )
    }
    groups["eligible_fundamentals"] = []
    if sum(map(len, groups.values())) != len(FEATURE_CATALOG):
        raise ContractMismatchError("An approved feature is missing from its Phase 6 group")

    report = {
        "schema_version": 1,
        "stage": "phase_6_step_6_2_feature_inventory",
        "status": "verified",
        "evidence_mode": evidence_mode,
        "input_identities": input_identities,
        "column_counts": {
            "dataset_columns": len(header),
            "approved_market_candidates": len(FEATURE_CATALOG),
            "eligible_fundamentals": 0,
            "excluded_columns": len(EXCLUDED_COLUMNS),
        },
        "groups": groups,
        "fundamental_gate": (
            "No fundamental column is present in this model-input dataset or approved "
            "for Phase 6. Steps 6.10-6.11 must pass the separate SEC point-in-time "
            "readiness gate before any fundamental can enter training."
        ),
        "availability_interpretation": (
            "Earliest usable dates are the first non-missing observations in the "
            "dataset, not evidence that every ticker is usable on that date."
        ),
        "feature_source": "src/feature_engineering/market_features.py",
        "code_sha256": {
            "src/model_training/feature_ablation/feature_inventory.py": sha256(__file__),
            "src/feature_engineering/market_features.py": sha256(
                "src/feature_engineering/market_features.py"
            ),
        },
        "features": inventory.loc[
            inventory["status"] == "approved_market_candidate"
        ].to_dict(orient="records"),
        "excluded": inventory.loc[inventory["status"] == "excluded"].to_dict(
            orient="records"
        ),
    }
    return report, inventory


def same_inventory_content(saved: dict[str, Any], current: dict[str, Any]) -> bool:
    """Compare generated inventory data while allowing its source to move.

    Formulas, groups, dates, missingness, and input identities must match
    exactly. The recorded source hashes remain visible as provenance, while a
    path-only source reorganization does not invalidate identical inventory
    content.
    """

    saved_content = dict(saved)
    current_content = dict(current)
    saved_content.pop("code_sha256", None)
    current_content.pop("code_sha256", None)
    return saved_content == current_content


def build_feature_inventory_report(
    dataset_path: Path = DEFAULT_DATASET,
    metadata_path: Path = DEFAULT_METADATA,
    contract_path: Path = DEFAULT_CONTRACT,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Validate and inventory every column in the frozen modeling dataset."""

    dataset_path, metadata_path, contract_path = map(
        Path, (dataset_path, metadata_path, contract_path)
    )
    current_contract = build_ablation_contract_report(
        dataset_path=dataset_path, metadata_path=metadata_path
    )
    saved_contract = _load_json(contract_path, "completed Phase 6.1 contract")
    if saved_contract != current_contract or saved_contract.get("status") != "verified":
        raise ContractMismatchError("Phase 6.1 contract is missing, stale, or not verified")

    metadata = _load_json(metadata_path, "dataset metadata")
    header = pd.read_csv(dataset_path, nrows=0).columns.tolist()
    expected_columns = set(FEATURE_CATALOG) | set(EXCLUDED_COLUMNS)
    if set(header) != expected_columns or len(header) != len(expected_columns):
        missing = sorted(expected_columns - set(header))
        unclassified = sorted(set(header) - expected_columns)
        raise ContractMismatchError(
            f"Dataset column inventory mismatch; missing={missing}, unclassified={unclassified}"
        )
    if list(FEATURE_CATALOG) != EXPECTED_FEATURE_ALLOWLIST:
        raise ContractMismatchError("Feature catalog differs from the frozen allowlist")
    if set(metadata["missingness"]) != set(header):
        raise ContractMismatchError("Metadata missingness does not cover every dataset column")

    values = pd.read_csv(dataset_path, usecols=["session_date", *FEATURE_CATALOG])
    rows: list[dict[str, Any]] = []
    for feature, definition in FEATURE_CATALOG.items():
        available = values[feature].notna()
        first = values.loc[available, "session_date"].min()
        last = values.loc[available, "session_date"].max()
        missing = int((~available).sum())
        expected_first, expected_missing = EXPECTED_AVAILABILITY[feature]
        if first != expected_first or missing != expected_missing:
            raise ContractMismatchError(
                f"{feature} availability mismatch: first={first}, missing={missing}"
            )
        if missing != metadata["missingness"][feature]:
            raise ContractMismatchError(f"{feature} missingness differs from metadata")
        rows.append(
            {
                "column": feature,
                "status": "approved_market_candidate",
                "group": definition["group"],
                "formula": definition["formula"],
                "lookback": definition["lookback"],
                "source_inputs": ", ".join(definition["source_inputs"]),
                "earliest_usable_date": first,
                "latest_available_date": last,
                "missing_rows": missing,
                "missing_percent": round(100 * missing / len(values), 6),
                "information_availability_rule": COMMON_AVAILABILITY_RULE,
                "exclusion_reason": "",
            }
        )

    for column in header:
        if column in FEATURE_CATALOG:
            continue
        category, reason = EXCLUDED_COLUMNS[column]
        rows.append(
            {
                "column": column,
                "status": "excluded",
                "group": category,
                "formula": "",
                "lookback": "",
                "source_inputs": "",
                "earliest_usable_date": "",
                "latest_available_date": "",
                "missing_rows": int(metadata["missingness"][column]),
                "missing_percent": round(
                    100 * metadata["missingness"][column] / metadata["rows"], 6
                ),
                "information_availability_rule": "Not eligible as a model input.",
                "exclusion_reason": reason,
            }
        )

    inventory = pd.DataFrame(rows)
    groups = {
        name: inventory.loc[
            (inventory["status"] == "approved_market_candidate")
            & (inventory["group"] == name),
            "column",
        ].tolist()
        for name in (
            "momentum",
            "volatility",
            "downside_trend",
            "market_relative",
            "volume",
        )
    }
    groups["eligible_fundamentals"] = []
    if sum(map(len, groups.values())) != len(FEATURE_CATALOG):
        raise ContractMismatchError("An approved feature is missing from its Phase 6 group")

    report = {
        "schema_version": 1,
        "stage": "phase_6_step_6_2_feature_inventory",
        "status": "verified",
        "input_identities": {
            "dataset": {"path": str(dataset_path), "sha256": sha256(dataset_path)},
            "metadata": {"path": str(metadata_path), "sha256": sha256(metadata_path)},
            "phase_6_1_contract": {
                "path": str(contract_path),
                "sha256": sha256(contract_path),
            },
        },
        "column_counts": {
            "dataset_columns": len(header),
            "approved_market_candidates": len(FEATURE_CATALOG),
            "eligible_fundamentals": 0,
            "excluded_columns": len(EXCLUDED_COLUMNS),
        },
        "groups": groups,
        "fundamental_gate": (
            "No fundamental column is present in the frozen model-input dataset "
            "or approved for Phase 6. Steps 6.10-6.11 must pass the separate SEC "
            "point-in-time readiness gate before any fundamental can enter training."
        ),
        "availability_interpretation": (
            "Earliest usable dates are the first non-missing observations in the "
            "frozen dataset, not evidence that every ticker is usable on that date."
        ),
        "feature_source": "src/feature_engineering/market_features.py",
        "code_sha256": {
            "src/model_training/feature_ablation/feature_inventory.py": sha256(__file__),
            "src/feature_engineering/market_features.py": sha256(
                "src/feature_engineering/market_features.py"
            ),
        },
        "features": inventory.loc[
            inventory["status"] == "approved_market_candidate"
        ].to_dict(orient="records"),
        "excluded": inventory.loc[inventory["status"] == "excluded"].to_dict(
            orient="records"
        ),
    }
    return report, inventory


def write_feature_inventory_report(
    json_path: Path = DEFAULT_INVENTORY_JSON,
    csv_path: Path = DEFAULT_INVENTORY_CSV,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Write new Step 6.2 evidence without replacing an existing inventory."""

    json_path, csv_path = Path(json_path), Path(csv_path)
    report, inventory = build_feature_inventory_report()
    json_text = json.dumps(report, indent=2) + "\n"
    csv_text = inventory.to_csv(index=False, lineterminator="\n")
    existing = [path for path in (json_path, csv_path) if path.exists()]
    if existing:
        if len(existing) != 2:
            raise FileExistsError(
                "Refusing to overwrite or silently repair incomplete Phase 6.2 evidence; "
                "preserve it and inspect "
                f"the missing companion file: {existing}"
            )
        saved_report = _load_json(json_path, "Phase 6.2 feature inventory")
        saved_csv = csv_path.read_text(encoding="utf-8")
        if not same_inventory_content(saved_report, report) or saved_csv != csv_text:
            raise FileExistsError(
                "Existing Phase 6.2 content differs from current inputs; "
                "choose a reviewed new version instead of overwriting it"
            )
        return saved_report, inventory
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_text, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")
    return report, inventory


def build_recovery_feature_inventory_report(
    dataset_path: Path,
    metadata_path: Path,
    protocol_path: Path,
    *,
    evidence_mode: str = (
        "reconstructed_phase_3_and_4_inputs; original_phase_5_reports_unavailable"
    ),
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Build Phase 6.2 evidence from a newly rebuilt Phase 3/4 package.

    The standard builder above remains the stricter route for the original
    frozen Phase 5 package.  This recovery route is intentionally explicit:
    it validates the rebuilt dataset against its own chronological protocol
    and records that it does not recreate missing historical Phase 5 files.
    """

    input_identities = _verified_recovery_inputs(
        Path(dataset_path), Path(metadata_path), Path(protocol_path)
    )
    return _build_inventory(
        Path(dataset_path),
        Path(metadata_path),
        input_identities,
        evidence_mode=evidence_mode,
    )


def write_recovery_feature_inventory_report(
    dataset_path: Path,
    metadata_path: Path,
    protocol_path: Path,
    json_path: Path,
    csv_path: Path,
    *,
    evidence_mode: str = (
        "reconstructed_phase_3_and_4_inputs; original_phase_5_reports_unavailable"
    ),
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Write recovery inventory evidence once, without overwriting a run."""

    json_path, csv_path = Path(json_path), Path(csv_path)
    report, inventory = build_recovery_feature_inventory_report(
        dataset_path,
        metadata_path,
        protocol_path,
        evidence_mode=evidence_mode,
    )
    json_text = json.dumps(report, indent=2) + "\n"
    csv_text = inventory.to_csv(index=False, lineterminator="\n")
    existing = [path for path in (json_path, csv_path) if path.exists()]
    if existing:
        if len(existing) != 2:
            raise FileExistsError(
                "Refusing to overwrite or silently repair incomplete Phase 6.2 recovery "
                f"evidence; inspect the missing companion file: {existing}"
            )
        saved_report = _load_json(json_path, "Phase 6.2 recovery inventory")
        saved_csv = csv_path.read_text(encoding="utf-8")
        if not same_inventory_content(saved_report, report) or saved_csv != csv_text:
            raise FileExistsError(
                "Existing Phase 6.2 recovery content differs from current inputs; "
                "choose a reviewed new version instead of overwriting it"
            )
        return saved_report, inventory
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_text, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")
    return report, inventory


def main() -> None:
    """Run either the original frozen route or an explicit recovery route."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-dataset", type=Path)
    parser.add_argument("--recovery-metadata", type=Path)
    parser.add_argument("--recovery-protocol", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    recovery_values = (
        args.recovery_dataset,
        args.recovery_metadata,
        args.recovery_protocol,
        args.output_json,
        args.output_csv,
    )
    if any(value is not None for value in recovery_values):
        if not all(value is not None for value in recovery_values):
            parser.error("all --recovery-* and --output-* arguments are required together")
        report, _ = write_recovery_feature_inventory_report(
            args.recovery_dataset,
            args.recovery_metadata,
            args.recovery_protocol,
            args.output_json,
            args.output_csv,
        )
    else:
        report, _ = write_feature_inventory_report()
    print(
        json.dumps(
            {
                "status": report["status"],
                "approved_market_candidates": report["column_counts"]["approved_market_candidates"],
                "excluded_columns": report["column_counts"]["excluded_columns"],
            }
        )
    )


if __name__ == "__main__":
    main()
