"""One offline command to clean, validate, build and verify price research data.

The default uses the registered, previously audited snapshot. It does not fetch
new data, change Shariah rules, train models or certify unresolved source flags.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from .reconciliation import save_json, sha256


def _inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError('Pipeline paths must stay inside their declared root')
    return path


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    required = {'schema_version', 'input_path', 'input_sha256', 'start', 'end'}
    if not required.issubset(config) or config['schema_version'] != 1:
        raise ValueError('Unsupported or incomplete pipeline configuration')
    if not re.fullmatch(r'[a-f0-9]{64}', config['input_sha256']):
        raise ValueError('The registered input needs an exact SHA-256 checksum')
    if (config['start'], config['end']) != ('2016-01-01', '2025-12-31'):
        raise ValueError('This pipeline preserves the existing 2016-2025 research definition')
    return config


def run(config_path, root='.', input_root=None, version=None):
    """Create new outputs only; preserve the frozen input and earlier runs."""
    import pandas as pd
    from .clean_data import clean_loop, price_pass, calendar_sessions, coverage_report
    from .price_audit import require_audited_prices, validate
    from .build_price_research import build
    from .verify_price_research import verify

    root = Path(root).resolve()
    input_root = Path(input_root).resolve() if input_root else root
    config_path = Path(config_path).resolve()
    config = load_config(config_path)
    version = version or 'data_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version):
        raise ValueError('Version must be one simple directory name')
    intermediate = _inside(root, Path('data/interim/prices') / version)
    processed = _inside(root, Path('data/processed') / version)
    report_folder = _inside(root, Path('reports/validation') / version)
    for folder in [intermediate, processed, report_folder]:
        if folder.exists():
            raise FileExistsError('Preserve the previous run; use a new version: ' + str(folder))
    source = _inside(input_root, config['input_path'])
    source_hash = sha256(source)
    if source_hash != config['input_sha256']:
        raise ValueError('Input differs from the registered audited snapshot; no output was written')

    # Check the evidence flags before cleaning can remove a problematic row.
    original = pd.read_csv(source)
    require_audited_prices(original)
    validate(original)
    report_folder.mkdir(parents=True, exist_ok=False)
    log_path = report_folder / 'pipeline.log'
    stage = 'clean'
    try:
        print('[1/4] Cleaning the registered price snapshot; existing evidence flags are preserved.')
        history = []
        cleaned, rejected = clean_loop(
            original, lambda frame: price_pass(frame, config['start'], config['end']),
            'prices', history, 6)
        if cleaned.empty:
            raise ValueError('No prices survived cleaning')
        intermediate.mkdir(parents=True, exist_ok=False)
        cleaned_path = intermediate / 'audited_prices.csv'
        cleaned.to_csv(cleaned_path, index=False)
        rejected.reindex(columns=list(original.columns) + ['rejection_reason', 'cleaning_pass']).to_csv(
            intermediate / 'quarantined_prices.csv', index=False)

        stage = 'validate'
        print('[2/4] Checking prices, evidence flags, exchange dates and coverage.')
        validate(cleaned)
        checked = require_audited_prices(cleaned)
        sessions, calendar = calendar_sessions(config['start'], config['end'], cleaned, False)
        if not checked.session_date.isin(sessions).all():
            raise ValueError('A price date is not a valid exchange session')
        coverage, gaps = coverage_report(cleaned, sessions, sorted(cleaned.ticker.unique()))
        coverage.to_csv(report_folder / 'price_coverage.csv', index=False)
        gaps.to_csv(report_folder / 'missing_sessions.csv', index=False)
        pd.DataFrame(history).to_csv(report_folder / 'cleaning_passes.csv', index=False)

        stage = 'build'
        print('[3/4] Building the existing 16 features and 20-session research targets.')
        with log_path.open('w', encoding='utf-8') as log, redirect_stdout(log):
            dataset = build(cleaned_path, root, version)

        stage = 'verify'
        print('[4/4] Independently verifying targets, chronological splits and training thresholds.')
        with log_path.open('a', encoding='utf-8') as log, redirect_stdout(log):
            checks = verify(cleaned_path, dataset, report_folder / 'independent_checks.json')

        if sha256(source) != source_hash:
            raise ValueError('The original input changed during the run')
        manifest = dict(
            status='completed_research_checks', version=version,
            config_sha256=sha256(config_path), source_path=config['input_path'],
            source_sha256=source_hash, cleaned_sha256=sha256(cleaned_path),
            original_input_unchanged=True, source_rows=len(original), cleaned_rows=len(cleaned),
            quarantined_rows=len(rejected), calendar=calendar,
            cleaning_converged=bool(history[-1]['stable']),
            missing_requested_sessions=len(gaps),
            false_share_basis_flags=int((~checked.share_basis_verified).sum()),
            false_return_transition_flags=int((~checked.return_transition_verified).sum()),
            dataset=str(dataset.relative_to(root)),
            cleaned_prices=str(cleaned_path.relative_to(root)),
            rows_independently_checked=checks['rows_independently_checked'],
            previous_source_audit_reused=True,
            original_raw_source_audit_rerun=False, screening_applied=False,
            global_action_or_issuer_certification=False, model_accuracy_measured=False,
            limitation='Reuses registered numerical evidence; unresolved flags and missing history remain unresolved.')
        save_json(report_folder / 'pipeline_manifest.json', manifest)
        print('Completed. Research rows:', manifest['rows_independently_checked'])
        print('Dataset:', dataset / 'research_rows.csv')
        print('Report:', report_folder / 'pipeline_manifest.json')
        return manifest
    except Exception as exc:
        save_json(report_folder / 'FAILED.json', dict(status='failed', stage=stage,
                  error_type=type(exc).__name__, error=str(exc), source_sha256=source_hash))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Project/output root')
    parser.add_argument('--config', type=Path, help='Default: configs/data_pipeline.json under root')
    parser.add_argument('--input-root', type=Path, help='Optional separate read-only data location')
    parser.add_argument('--version', help='New output version; generated automatically when omitted')
    parser.add_argument('--plan', action='store_true', help='Show the workflow without reading data or writing outputs')
    args = parser.parse_args(argv)
    config_path = args.config or args.root / 'configs/data_pipeline.json'
    if args.plan:
        config = load_config(config_path)
        print('Input:', config['input_path'])
        print('Steps: clean -> validate -> build research dataset -> independently verify')
        print('Offline; source audit reused; original inputs and previous runs are preserved.')
        return
    try:
        return run(config_path, args.root, args.input_root, args.version)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print('Pipeline stopped:', exc, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
