"""Rebuild 16 predictors and 20-session targets from numerically audited prices.

Keeps original inputs intact and writes a new data/processed/<version> directory.
This is price research; SEC screening evidence is not a model predictor here.
"""
import argparse
import json
from pathlib import Path
import exchange_calendars as xc
import numpy as np
import pandas as pd

from .reconciliation import COMPANY_SYMBOLS, save_json, sha256
from .training_inputs import require_audited_prices
from ..features.core import FEATURES, build_features
from ..labels.targets import build_targets, split_and_label


def build_table(prices, sessions):
    prices = require_audited_prices(prices)
    features = build_features(prices, sessions)
    targets = build_targets(prices, sessions)
    frame = features.merge(targets, on=['ticker', 'as_of_date'], validate='one_to_one')
    spy = prices[prices.ticker.eq('SPY')].set_index('session_date').reindex(sessions)
    benchmark_returns = spy.adjusted_close.pct_change(fill_method=None).where(
        spy.return_transition_verified.fillna(False))
    benchmark_good = benchmark_returns.notna().astype(int).rolling(20, min_periods=20).sum().shift(-20).eq(20)
    benchmark_future = (spy.adjusted_close.shift(-20)/spy.adjusted_close-1).where(benchmark_good)
    frame['future_excess_return_20d'] = frame.future_return_20d-frame.as_of_date.map(benchmark_future)
    invalid_benchmark = ~np.isfinite(frame.future_excess_return_20d)
    frame.loc[invalid_benchmark, 'labels_ready'] = False
    frame.loc[invalid_benchmark, 'exclusion_reason'] = 'future_benchmark_gap_or_unresolved_action'
    frame, cutoffs = split_and_label(frame)
    train = frame[frame.split.eq('train')]
    lo, hi = train.future_excess_return_20d.quantile([1/3, 2/3], interpolation='linear')
    if not np.isfinite([lo, hi]).all() or hi <= lo:
        raise ValueError('Invalid training-only excess-return thresholds')
    used = frame.split.ne('excluded')
    frame['excess_return_class'] = None
    frame.loc[used, 'excess_return_class'] = np.where(frame.loc[used, 'future_excess_return_20d'] <= lo, 'low',
        np.where(frame.loc[used, 'future_excess_return_20d'] <= hi, 'medium', 'high'))
    cutoffs['future_excess_return_20d'] = dict(lower_cutoff=float(lo), upper_cutoff=float(hi),
        fit_row_count=len(train), quantile_method='linear', class_order=['low','medium','high'])
    columns = FEATURES+['future_return_20d', 'future_volatility_20d', 'future_excess_return_20d']
    if not np.isfinite(frame.loc[used, columns]).all().all():
        raise ValueError('Eligible rows contain missing or nonfinite values')
    return frame.sort_values(['as_of_date', 'ticker']).reset_index(drop=True), cutoffs


def build(prices_path, repo, version):
    repo, prices_path = Path(repo), Path(prices_path)
    prices = pd.read_csv(prices_path)
    if set(prices.ticker) != set(COMPANY_SYMBOLS+['SPY']):
        raise ValueError('Expected the registered 50 companies and separate SPY prices')
    if Path(version).name != version or version in {'.','..'}:
        raise ValueError('Version must be one directory name')
    output = repo/'data/processed'/version
    if output.exists():
        raise FileExistsError('Preserve the previous run: choose a new version')
    sessions = xc.get_calendar('XNYS', start='2015-01-01', end='2026-12-31').sessions
    sessions = sessions[(sessions >= pd.Timestamp('2016-01-01')) & (sessions <= pd.Timestamp('2025-12-31'))]
    frame, cutoffs = build_table(prices, sessions)
    output.mkdir(parents=True, exist_ok=False)
    frame.to_csv(output/'feature_target_audit.csv', index=False)
    used = frame[frame.split.ne('excluded')]
    used.to_csv(output/'research_rows.csv', index=False)
    groups = {}
    for name, group in used.groupby('split'):
        groups[name] = dict(rows=len(group), companies=group.ticker.nunique(),
            first_feature_date=str(group.as_of_date.min().date()), last_feature_date=str(group.as_of_date.max().date()),
            last_label_date=str(group.label_end_date.max().date()))
    report = dict(input_sha256=sha256(prices_path), input_rows=len(prices),
        feature_order=FEATURES, horizon_sessions=20, eligible_rows=len(used),
        excluded_rows=len(frame)-len(used), splits=groups,
        output_sha256=sha256(output/'research_rows.csv'), label_thresholds=cutoffs,
        excluded_reasons=frame.loc[frame.split.eq('excluded'),'exclusion_reason'].value_counts().to_dict(),
        numerically_audited=True, global_action_coverage_certified=False, historical_issuer_history_certified=False,
        screening_applied=False, accuracy_measured_this_run=False,
        test_period_previously_inspected=True,
        limitation='Research dataset with unresolved action windows excluded; not complete historical issuer/action certification or a promise of forecast accuracy.')
    save_json(output/'metadata.json', report)
    save_json(repo/'reports/validation'/version/'dataset_manifest.json', report)
    print(json.dumps(report, indent=2))
    return output


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--version', required=True)
    args=p.parse_args()
    build(args.prices, args.repo, args.version)
