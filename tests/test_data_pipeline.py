"""Guard the new entry point against changed evidence and destructive reruns."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from src.data.pipeline import run, main
from src.data.sec import extract_fundamentals, download_companyfacts


def fixture_config(root, **changes):
    source = root / 'data/interim/fixture.csv'
    source.parent.mkdir(parents=True)
    pd.DataFrame([dict(ticker=ticker, session_date='2020-01-02', open=10., high=10.,
        low=10., close=10., adjusted_close=10., volume=100, dataset_version='fixture',
        share_basis_verified=True, return_transition_verified=False)
        for ticker in ['AAPL', 'SPY']]).to_csv(source, index=False)
    config = dict(schema_version=1, input_path='data/interim/fixture.csv',
                  input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  start='2016-01-01', end='2025-12-31')
    config.update(changes)
    path = root / 'config.json'
    path.write_text(json.dumps(config))
    return path, source


def test_changed_input_stops_before_creating_outputs(tmp_path):
    config, source = fixture_config(tmp_path)
    source.write_bytes(source.read_bytes() + b'\n')
    before = source.read_bytes()
    with pytest.raises(ValueError, match='registered audited snapshot'):
        run(config, tmp_path, version='test')
    assert source.read_bytes() == before
    assert not (tmp_path / 'data/processed').exists()
    assert not (tmp_path / 'reports').exists()


@pytest.mark.parametrize('version', ['../escape', '/absolute', 'two/folders'])
def test_version_cannot_escape_output_roots(tmp_path, version):
    config, _ = fixture_config(tmp_path)
    with pytest.raises(ValueError, match='directory name'):
        run(config, tmp_path, version=version)
    assert not (tmp_path / 'reports').exists()


def test_existing_run_is_not_overwritten(tmp_path):
    config, _ = fixture_config(tmp_path)
    previous = tmp_path / 'data/processed/previous'
    previous.mkdir(parents=True)
    sentinel = previous / 'research_rows.csv'
    sentinel.write_bytes(b'previous research result')
    with pytest.raises(FileExistsError, match='Preserve'):
        run(config, tmp_path, version='previous')
    assert sentinel.read_bytes() == b'previous research result'


def test_unknown_evidence_cannot_be_removed_or_promoted_by_cleaning(tmp_path):
    config_path, source = fixture_config(tmp_path)
    frame = pd.read_csv(source)
    frame['share_basis_verified'] = 'unknown'
    frame.to_csv(source, index=False)
    config = json.loads(config_path.read_text())
    config['input_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='boolean evidence'):
        run(config_path, tmp_path, version='test')
    assert not (tmp_path / 'reports').exists()


def test_plan_needs_no_data_and_writes_nothing(tmp_path, capsys):
    config, source = fixture_config(tmp_path)
    source.unlink()
    main(['--root', str(tmp_path), '--config', str(config), '--plan'])
    assert 'independently verify' in capsys.readouterr().out
    assert not (tmp_path / 'reports').exists()


def test_extract_keeps_debt_components_and_filing_dates_separate(tmp_path):
    source = tmp_path / 'raw'
    source.mkdir()
    facts = {'entityName': 'Synthetic fixture only', 'facts': {'us-gaap': {
        concept: {'units': {'USD': [dict(val=value, end='2024-12-31', filed='2025-02-01',
        form='10-K', fy=2024, fp='FY', accn='fixture')]}}
        for concept, value in [('Assets', 100), ('LongTermDebtCurrent', 10),
                               ('LongTermDebtNoncurrent', 20)]}}}
    (source / 'FIXTURE_companyfacts.json').write_text(json.dumps(facts))
    out = tmp_path / 'intermediate'
    extract_fundamentals(source, out)
    path = out / 'sec_historical_fundamentals_long.csv'
    frame = pd.read_csv(path)
    assert frame.query("field == 'total_debt'").value.tolist() == [10, 20]
    assert frame.filing_date.eq('2025-02-01').all()
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        extract_fundamentals(source, out)
    assert path.read_bytes() == before


def test_sec_download_refuses_existing_raw_folder_before_network(tmp_path, monkeypatch):
    sentinel = tmp_path / 'saved.json'
    sentinel.write_bytes(b'original')
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('Unexpected network call'))
    with pytest.raises(FileExistsError, match='immutable'):
        download_companyfacts(tmp_path)
    assert sentinel.read_bytes() == b'original'


def test_parser_and_screening_modules_import_without_network_or_credentials(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    code = """
import sys
sys.path.insert(0, sys.argv[1])
import socket, urllib.request
def refuse(*args, **kwargs):
    raise AssertionError('Import triggered a provider request')
socket.socket.connect = refuse
urllib.request.urlopen = refuse
import src.data.sec
import src.data.screening_disclosures
import src.screening.source_facts
import src.screening.run_yasaar
"""
    result = subprocess.run([sys.executable, '-c', code, str(repo)], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())
