"""Numerical share-basis and action reconciliation; not universal issuer certification."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .reconciliation import save_json, sha256


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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices', type=Path, required=True)
    p.add_argument('--raw', type=Path, required=True)
    p.add_argument('--actions', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    args = p.parse_args()
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


if __name__ == '__main__':
    main()
