"""Versioned phase 3 labels on the preserved market-feature snapshot."""
import argparse
import json
from pathlib import Path
import tempfile

import exchange_calendars as xc
import numpy as np
import pandas as pd

from src.features.market import FEATURE_COLUMNS
from src.features.build_dataset import sha256, VALIDATION_START, TEST_START

DEFAULT_FEATURES = Path('data/modeling/market_features_20261023T012858924857Z/market_features.csv')


def outcomes(frame):
    out = frame.copy()
    dates = pd.to_datetime(out.session_date)
    cal = xc.get_calendar('XNYS', start=dates.min()-pd.Timedelta(days=10), end=dates.max()+pd.Timedelta(days=10))
    sessions = cal.sessions_in_range(dates.min(), dates.max()).tz_localize(None)
    ends = pd.Series(sessions, index=sessions).shift(-20)
    out['target_window_end'] = dates.map(ends).dt.strftime('%Y-%m-%d')
    for name in ['return_next_20d', 'risk_volatility_next_20d']:
        out[name] = np.nan
    for _, group in out.groupby('ticker'):
        index = pd.DatetimeIndex(pd.to_datetime(group.session_date))
        close = pd.Series(group.adjusted_close.to_numpy(), index=index).reindex(sessions)
        daily = close.pct_change(fill_method=None)
        vol = daily.rolling(20, min_periods=20).std(ddof=1).shift(-20)*np.sqrt(252)
        ret = (close.shift(-20)/close-1).where(vol.notna())
        out.loc[group.index, 'return_next_20d'] = ret.reindex(index).to_numpy()
        out.loc[group.index, 'risk_volatility_next_20d'] = vol.reindex(index).to_numpy()
    return out


def relative_classes(frame):
    out = frame.copy()
    eligible = out.volume.gt(0) & out.return_next_20d.notna()
    values = out.return_next_20d.where(eligible)
    count = values.groupby(out.session_date).transform('count')
    rank = values.groupby(out.session_date).rank(method='average')
    valid = eligible & count.ge(45) & out.active_peer_count.ge(45)
    out['outcome_peer_count'] = count
    out['relative_return_class'] = pd.Series(pd.NA, index=out.index, dtype='Int64')
    out.loc[valid, 'relative_return_class'] = np.select([rank[valid].le(count[valid]/3), rank[valid].le(2*count[valid]/3)], [0, 1], default=2)
    out['return_label_reason'] = np.select([out.volume.le(0), out.return_next_20d.isna(), out.active_peer_count.lt(45), count.lt(45)], ['inactive', 'incomplete_future_window', 'activity_quorum', 'outcome_quorum'], default='available')
    return out


def risk_classes(frame):
    out = frame.copy()
    end = pd.to_datetime(out.target_window_end)
    purge = (out.nominal_split.eq('train') & end.ge(VALIDATION_START)) | (out.nominal_split.eq('validation') & end.ge(TEST_START))
    out['dataset_split'] = out.nominal_split.mask(purge, 'purged')
    complete = out[FEATURE_COLUMNS].notna().all(axis=1)
    training = out.dataset_split.eq('train') & complete & out.risk_volatility_next_20d.notna()
    low, high = out.loc[training, 'risk_volatility_next_20d'].quantile([1/3, 2/3]).to_numpy()
    if not np.isfinite([low, high]).all() or low >= high:
        raise ValueError('Training risk boundaries must be finite and distinct')
    out['risk_class'] = pd.Series(pd.NA, index=out.index, dtype='Int64')
    valid = out.risk_volatility_next_20d.notna()
    values = out.loc[valid, 'risk_volatility_next_20d']
    out.loc[valid, 'risk_class'] = np.select([values.le(low), values.le(high)], [0, 1], default=2)
    for task, target in [('return', 'relative_return_class'), ('risk', 'risk_class')]:
        out[task+'_eligibility_reason'] = np.select([purge, ~complete, out[target].isna()], ['purged_window', 'feature_warmup_or_missing', 'missing_label'], default='eligible')
        out[task+'_eligible'] = out[task+'_eligibility_reason'].eq('eligible')
    return out, {'low_upper_inclusive': float(low), 'medium_upper_inclusive': float(high), 'training_rows': int(training.sum())}


def model_inputs(frame, columns=None):
    columns = FEATURE_COLUMNS if columns is None else list(columns)
    if set(columns)-set(FEATURE_COLUMNS):
        raise ValueError('Non-allowlisted model inputs')
    return frame[columns].copy()


def build(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError(output)
    parent_metadata = json.loads((source.parent/'features_metadata.json').read_text())
    if sha256(source) != parent_metadata['output_sha256']:
        raise ValueError('Feature snapshot checksum mismatch')
    original = pd.read_csv(source)
    if original.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Duplicate keys')
    result, boundaries = risk_classes(relative_classes(outcomes(original)))
    pd.testing.assert_frame_equal(original, result[original.columns])
    model_inputs(result)
    metadata = dict(parent_metadata)
    metadata.update(stage='features_and_labels', ready_for_training=False,
        readiness_note='Eligible rows support development research; phase 4 fold definitions remain required.',
        parent_features_sha256=sha256(source), risk_boundaries=boundaries,
        return_rule='Active and outcome quorum >=45; average rank <= n/3:0, <=2n/3:1, else 2; ties stay together.',
        risk_rule='Sample std of adjusted returns t+1..t+20 * sqrt(252); training-only linear tertiles.',
        return_formula='adjusted_close(t+20)/adjusted_close(t)-1; complete future window required',
        feature_definitions_source='src/features/market.py',
        class_names={'return': ['Lower','Middle','Higher'], 'risk': ['Low','Medium','High']},
        split_warning='Actual target end dates purged at development boundaries. Reused test is not blind.',
        excluded_from_features=[c for c in result if c not in FEATURE_COLUMNS],
        missingness=result.isna().sum().astype(int).to_dict(),
        split_counts=result.dataset_split.value_counts().to_dict(),
        eligible_counts={t: int(result[t+'_eligible'].sum()) for t in ['return','risk']},
        class_counts={c: {str(k): int(v) for k,v in result[c].value_counts().items()} for c in ['relative_return_class','risk_class']})
    metadata['code_sha256'] = {p: sha256(p) for p in ['src/labels/phase3.py','src/features/market.py','src/features/build_dataset.py']}
    json.dumps(metadata)  # Validate serialization before writing an artifact.
    output.mkdir(parents=True)
    destination = output/'market_features_and_labels.csv'
    result.to_csv(destination, index=False)
    metadata['output_sha256'] = sha256(destination)
    (output/'dataset_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, default=DEFAULT_FEATURES)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    first = build(args.features, args.output_dir)
    with tempfile.TemporaryDirectory() as temporary:
        second = build(args.features, Path(temporary)/'reproduction')
    if first != second:
        raise RuntimeError('Reproduction metadata or CSV hash differs')
    print(json.dumps({'reproduced': True, 'output': str(args.output_dir), 'eligible_counts': first['eligible_counts'], 'risk_boundaries': first['risk_boundaries']}))
