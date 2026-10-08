"""Require explicit price checks before building model inputs.

False flags are retained: feature and target builders exclude affected windows.
Numerical reconciliation is not universal corporate-action certification.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .check_price_actions import audit, events_from_pages
from .collect_price_bases import validate
from .reconciliation import save_json, sha256


def checked_bool(series, name):
    mapping = {'true': True, 'false': False, '1': True, '0': False}
    result = series.astype(str).str.strip().str.lower().map(mapping)
    if result.isna().any():
        raise ValueError(f'Invalid or missing boolean evidence in {name}')
    return result.astype(bool)


def require_audited_prices(prices):
    required = {'ticker', 'session_date', 'close', 'adjusted_close', 'volume',
                'dataset_version', 'share_basis_verified', 'return_transition_verified'}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f'Unaudited training prices: missing {sorted(missing)}. '
                         'Use audited_prices.csv; never default verification to True.')
    prices = prices.copy()
    if prices.ticker.isna().any() or prices.dataset_version.isna().any():
        raise ValueError('Missing instrument or dataset version')
    if prices.dataset_version.nunique() != 1 or 'SPY' not in set(prices.ticker):
        raise ValueError('One dataset version and separate SPY bars are required')
    prices['session_date'] = pd.to_datetime(prices.session_date, errors='raise')
    if prices.session_date.isna().any() or prices.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Missing or duplicate session keys')
    for name in ['close', 'adjusted_close', 'volume']:
        prices[name] = pd.to_numeric(prices[name], errors='raise')
    if not np.isfinite(prices[['close', 'adjusted_close', 'volume']]).all().all():
        raise ValueError('Nonfinite price or volume')
    if (prices[['close', 'adjusted_close']] <= 0).any().any() or (prices.volume < 0).any():
        raise ValueError('Invalid price or volume')
    for name in ['share_basis_verified', 'return_transition_verified']:
        prices[name] = checked_bool(prices[name], name)
    return prices


def checked_pages(folder, allowed_statuses):
    folder = Path(folder)
    metadata = json.loads((folder / 'metadata.json').read_text())
    if metadata.get('status') not in allowed_statuses or not metadata.get('pages'):
        raise ValueError(f'Incomplete source evidence: {folder}')
    for page in metadata['pages']:
        name = page['file']
        if Path(name).name != name or sha256(folder / name) != page['sha256']:
            raise ValueError(f'Invalid source page or hash: {folder}')
    return metadata


def prepare(prices_path, raw_path, actions_folder, repo):
    prices_path, raw_path = Path(prices_path), Path(raw_path)
    metadata = checked_pages(raw_path.parent, {'downloaded'})
    if sha256(raw_path) != metadata.get('csv_sha256'):
        raise ValueError('Raw reference CSV does not match its download metadata')
    checked_pages(actions_folder, {'downloaded_requires_event_review'})
    prices = pd.read_csv(prices_path)
    validate(prices)
    frame, checks = audit(prices, pd.read_csv(raw_path), events_from_pages(Path(actions_folder)))
    require_audited_prices(frame)
    # A new output preserves every earlier snapshot and report.
    from uuid import uuid4
    version = 'training_audit_' + uuid4().hex
    output = Path(repo) / 'data/interim/prices' / version
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'audited_prices.csv'
    frame.to_csv(target, index=False)
    save_json(Path(repo) / 'reports/validation' / version / 'input_audit.json', dict(
        scope='Numerical reconciliation against explicitly supplied saved evidence',
        global_action_coverage_certified=False,
        source_prices=str(prices_path), source_prices_sha256=sha256(prices_path),
        raw_reference=str(raw_path), raw_reference_sha256=sha256(raw_path),
        actions_folder=str(actions_folder), output_sha256=sha256(target),
        rows=len(frame), share_basis_failed_rows=int((~frame.share_basis_verified).sum()),
        unchecked_transitions=int((~frame.return_transition_verified).sum()), checks=checks))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--actions', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(prepare(args.prices, args.raw, args.actions, args.repo))


if __name__ == '__main__':
    main()
