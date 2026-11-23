import json
from pathlib import Path


HANDOFF = Path("configs/phase7_handoff_v1.json")


def test_phase7_handoff_has_unique_repository_relative_artifacts_and_hashes():
    contract = json.loads(HANDOFF.read_text(encoding="utf-8"))
    artifacts = contract["required_local_artifacts"]
    paths = [item["path"] for item in artifacts]

    assert contract["status"] == "prepared_requires_source_commit_and_artifact_transfer"
    assert len(paths) == len(set(paths)) == 11
    assert all(not Path(path).is_absolute() for path in paths)
    assert all(len(item["sha256"]) == 64 for item in artifacts)
    assert paths[0].endswith("phase6_expanded_features_v1/market_features_and_labels.csv")
    assert contract["phase7_output_root"] == (
        "reports/model_evaluation/phase7_candidate_tuning_v1"
    )


def test_phase7_handoff_requires_current_freeze_and_excludes_secrets():
    contract = json.loads(HANDOFF.read_text(encoding="utf-8"))
    repository_files = set(contract["required_versioned_repository_files"])
    exclusions = " ".join(contract["excluded_from_handoff"]).lower()

    assert "configs/phase6_feature_freeze_v2.json" in repository_files
    assert "docs/PHASE7_RUNBOOK.md" in repository_files
    assert "decision.md" in repository_files
    assert ".env" in exclusions
    assert ".venv" in exclusions
    assert "credentials" in exclusions
    assert "must not rebuild" in contract["dataset_policy"].lower()
    assert "no-fit" in contract["recipient_first_action"].lower()


def test_phase6_has_one_canonical_document():
    phase6_documents = sorted(Path("docs").glob("PHASE6*.md"))

    assert phase6_documents == [Path("docs/PHASE6.md")]
