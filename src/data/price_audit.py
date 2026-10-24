"""Validate price schemas and audit saved prices/actions before model preparation.

The existing calculations and strict evidence gates are retained. Use this
module with --prices/--raw/--actions, or its actions subcommand for diagnostics.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from .reconciliation import save_json, sha256

def validate(frame):
    if frame.empty:
        raise ValueError('No bars returned')
    if frame.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Duplicate sessions returned')
    columns = ['open', 'high', 'low', 'close', 'volume']
    values = frame[columns].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(values).all().all():
        raise ValueError('Nonfinite price/volume')
    if (values[['open', 'high', 'low', 'close']] <= 0).any().any() or (values.volume < 0).any():
        raise ValueError('Invalid price/volume')
    if ((values.high < values[['open', 'close', 'low']].max(axis=1)) |
            (values.low > values[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC values')

def events_from_pages(folder):
    events = {}
    for path in sorted(folder.glob('page_*.json')):
        for kind, records in json.loads(path.read_text()).get('corporate_actions', {}).items():
            for record in records:
                key = record.get('id', json.dumps(record, sort_keys=True))
                if key in events and events[key] != (kind, record):
                    raise ValueError('Conflicting corporate-action versions require review')
                events[key] = kind, record
    return list(events.values())

def audit(prices, raw, events):
    keys = ['ticker', 'session_date']
    if prices.duplicated(keys).any() or raw.duplicated(keys).any():
        raise ValueError('Duplicate price keys')
    if set(map(tuple, prices[keys].values)) != set(map(tuple, raw[keys].values)):
        raise ValueError('Raw and adjusted series have different sessions')
    frame = prices.merge(raw, on=keys, validate='one_to_one').sort_values(keys)
    if not np.isfinite(frame[['close', 'adjusted_close', 'raw_close', 'volume', 'raw_volume']]).all().all():
        raise ValueError('Nonfinite reference prices')
    if (frame[['close', 'adjusted_close', 'raw_close']] <= 0).any().any():
        raise ValueError('Nonpositive reference price')
    if (frame[['volume', 'raw_volume']] < 0).any().any():
        raise ValueError('Negative volume')
    # Raw dollar turnover should equal split-only turnover within cent-price and
    # integer-share rounding. This independently tests the matching share bases.
    factor_lower = (frame.raw_close-.0051)/(frame.close+.0051)
    factor_upper = (frame.raw_close+.0051)/(frame.close-.0051)
    frame['share_basis_verified'] = (
        (frame.volume >= frame.raw_volume * factor_lower - 1.01) &
        (frame.volume <= frame.raw_volume * factor_upper + 1.01))
    frame['return_transition_verified'] = False
    frame['action_review_reason'] = ''
    checks = []
    for ticker, group in frame.groupby('ticker', sort=False):
        action_dates = {}
        for kind, event in events:
            symbol = event.get('symbol', event.get('source_symbol'))
            if symbol != ticker:
                continue
            date = event.get('ex_date', event.get('effective_date'))
            if date:
                action_dates.setdefault(date, []).append((kind, event))
        for pos in range(1, len(group)):
            before, after = group.iloc[pos-1], group.iloc[pos]
            date = after.session_date
            today = action_dates.get(date, [])
            # Ratios of cent-rounded adjusted values yield an uncertainty interval.
            lower = ((before.adjusted_close-.0051)/(before.close+.0051)) / (
                     (after.adjusted_close+.0051)/(after.close-.0051))
            upper = ((before.adjusted_close+.0051)/(before.close-.0051)) / (
                     (after.adjusted_close-.0051)/(after.close+.0051))
            dividends = [event for kind, event in today if kind == 'cash_dividends']
            unsupported = [kind for kind, event in today if kind not in {
                'cash_dividends', 'forward_splits', 'reverse_splits'}]
            expected = 1 - sum(event['rate'] for event in dividends)/before.raw_close
            splits = [event for kind, event in today if kind in {'forward_splits', 'reverse_splits'}]
            expected_split = float(np.prod([event['new_rate']/event['old_rate'] for event in splits]))
            split_lower = ((before.raw_close-.0051)/(before.close+.0051)) / (
                          (after.raw_close+.0051)/(after.close-.0051))
            split_upper = ((before.raw_close+.0051)/(before.close-.0051)) / (
                          (after.raw_close-.0051)/(after.close+.0051))
            split_passed = split_lower <= expected_split <= split_upper
            passed = not unsupported and expected > 0 and lower <= expected <= upper and split_passed
            reason = ('unsupported_action:'+','.join(unsupported) if unsupported else
                      'split_change_not_explained_by_saved_splits' if not split_passed else
                      '' if passed else 'adjustment_change_not_explained_by_saved_dividends')
            frame.loc[after.name, 'return_transition_verified'] = passed
            frame.loc[after.name, 'action_review_reason'] = reason
            if today or not passed:
                checks.append(dict(ticker=ticker, session_date=date,
                    kinds=[kind for kind, event in today], verified=bool(passed), reason=reason,
                    ratio_lower=float(lower), ratio_upper=float(upper), expected=float(expected),
                    split_ratio_lower=float(split_lower), split_ratio_upper=float(split_upper),
                    expected_split_ratio=expected_split))
        frame.loc[group.index[0], 'action_review_reason'] = 'first_observation_no_prior_transition'
    frame['adjustment_verified'] = frame.share_basis_verified & frame.return_transition_verified
    frame['data_quality_flags'] = frame.action_review_reason
    return frame, checks

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

def action_main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices', type=Path, required=True)
    p.add_argument('--raw', type=Path, required=True)
    p.add_argument('--actions', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    args = p.parse_args(argv)
    frame, checks = audit(pd.read_csv(args.prices), pd.read_csv(args.raw), events_from_pages(args.actions))
    target = args.repo/'data/interim/readiness_v1'
    target.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target/'audited_prices.csv', index=False)
    summary = dict(rows=len(frame), instruments=frame.ticker.nunique(),
        share_basis_failed_rows=int((~frame.share_basis_verified).sum()),
        unresolved_return_transitions=int((~frame.return_transition_verified).sum())-frame.ticker.nunique(),
        scope='Cent-rounding numerical reconciliation against raw prices and saved actions; unresolved transitions excluded',
        global_action_coverage_certified=False, checks=checks,
        source_hashes={str(args.prices):sha256(args.prices),str(args.raw):sha256(args.raw)})
    save_json(args.repo/'reports/validation/readiness_v1/price_actions.json', summary)
    print({k:v for k,v in summary.items() if k not in ['checks','source_hashes']})

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--actions', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    print(prepare(args.prices, args.raw, args.actions, args.repo))

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'actions':
        action_main(sys.argv[2:])
    else:
        main()
