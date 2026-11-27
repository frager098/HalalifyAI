import hashlib
import json

from src.data_pipeline.collect_sec_point_in_time_snapshot import load_config, ticker_mapping
from src.data_pipeline.validate_sec_point_in_time_snapshot import validate_snapshot


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_snapshot(tmp_path, *, tamper=False, missing_submissions=False):
    root = tmp_path / "snapshot"
    root.mkdir()
    files, tickers = [], [f"T{i:02d}" for i in range(50)]
    for number, ticker in enumerate(tickers, start=1):
        cik = str(number).zfill(10)
        for kind, name in (("companyfacts", f"{ticker}_companyfacts.json"),
                           ("submissions", f"{ticker}_submissions.json")):
            if missing_submissions and ticker == "T00" and kind == "submissions":
                continue
            path = root / name
            path.write_text(json.dumps({"cik": cik}), encoding="utf-8")
            files.append({"file": name, "kind": kind, "ticker": ticker, "cik": cik,
                          "sha256": digest(path), "bytes": path.stat().st_size})
    if tamper:
        (root / "T01_companyfacts.json").write_text("changed", encoding="utf-8")
    metadata = {
        "schema_version": 1, "status": "complete", "requested_tickers": tickers,
        "files": files, "failed": [], "availability_rule": "next day",
        "approved_candidate_concepts": {"assets_usd": "Assets"},
        "not_approved_for_model_features": ["debt"], "important_limitations": [],
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return root


def test_config_has_exactly_50_unique_tickers():
    config = load_config()
    assert len(config["tickers"]) == len(set(config["tickers"])) == 50


def test_ticker_mapping_normalizes_cik_and_ticker():
    assert ticker_mapping({"0": {"ticker": "aapl", "cik_str": 320193}}) == {"AAPL": "0000320193"}


def test_complete_snapshot_passes(tmp_path):
    assert validate_snapshot(make_snapshot(tmp_path))["status"] == "passed"


def test_changed_file_fails_checksum(tmp_path):
    report = validate_snapshot(make_snapshot(tmp_path, tamper=True))
    assert report["status"] == "failed"
    assert report["checksum_failures"] == ["T01_companyfacts.json"]


def test_missing_submissions_fails(tmp_path):
    report = validate_snapshot(make_snapshot(tmp_path, missing_submissions=True))
    assert report["status"] == "failed"
    assert report["tickers_missing_companyfacts_or_submissions"] == {"T00": ["submissions"]}
