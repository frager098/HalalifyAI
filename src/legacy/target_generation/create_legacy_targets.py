"""Create two future-risk targets on one shared, chronologically split table.
Run: python -m src.legacy.target_generation.create_legacy_targets --prices data/processed/cleaned_market_data/<run_name>/prices_clean.csv
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import exchange_calendars as xc

TARGETS = [
    'risk_volatility_next_20d',
    'risk_class_next_20d',
    'return_next_20d',
    'return_class_next_20d',
    'excess_return_next_20d',
    'excess_return_class_next_20d'
]
# Deliberately narrow feature list. Targets, future dates and metadata are excluded.
FEATURES = ['open','high','low','close','volume','adjusted_close',
            'split_close_return','provider_all_adjusted_return','spy_return']


def future_volatility(returns, horizon=20):
    """At t, sample standard deviation of r[t+1:t+h+1], annualized."""
    return returns.rolling(horizon, min_periods=horizon).std(ddof=1).shift(-horizon) * np.sqrt(252)


def future_return(close, horizon=20):
    """At t, simple 20-session return P[t+h] / P[t] - 1."""
    return close.shift(-horizon) / close - 1


def classify(values, low, high):
    result = pd.Series(pd.NA, index=values.index, dtype='string')
    valid = values.notna()
    result.loc[valid & values.le(low)] = 'low'
    result.loc[valid & values.gt(low) & values.le(high)] = 'medium'
    result.loc[valid & values.gt(high)] = 'high'
    return result


def build_targets(prices_path, output_dir=None, horizon=20):
    if horizon != 20:
        raise ValueError('This version names its targets next_20d and requires horizon=20.')
    prices_path = Path(prices_path).resolve()
    df = pd.read_csv(prices_path, dtype={'ticker':'string','session_date':'string'})
    if df.duplicated(['ticker','session_date']).any():
        raise ValueError('Duplicate ticker/date keys.')
    required = {'ticker','session_date','adjusted_close',*FEATURES[:-1]}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required-set(df.columns)}')
    if not df.ticker.eq('SPY').any():
        raise ValueError('SPY benchmark missing.')
    start, end = pd.to_datetime(df.session_date).agg(['min','max'])
    cal = xc.get_calendar('XNYS',start=start-pd.Timedelta(days=10),end=end+pd.Timedelta(days=10))
    sessions = cal.sessions_in_range(start,end).tz_localize(None).normalize()
    if len(sessions) < horizon * 5:
        raise ValueError('Insufficient sessions for three chronological splits.')
    if not pd.to_datetime(df.session_date).isin(sessions).all():
        raise ValueError('Input contains unexpected exchange dates.')
    train_boundary = int(len(sessions)*0.70)
    test_boundary = int(len(sessions)*0.85)
    validation_start, test_start = sessions[train_boundary], sessions[test_boundary]
    label_end_map = pd.Series(sessions, index=sessions).shift(-horizon)
    spy = df[df.ticker.eq('SPY')].copy()
    spy.index = pd.to_datetime(spy.session_date)
    spy_close = spy.adjusted_close.reindex(sessions)
    spy_returns = spy_close.pct_change(fill_method=None)
    spy_future_returns = future_return(spy_close, horizon)
    parts = []
    # SPY provides a benchmark feature. The modeled instruments are the companies.
    for ticker, block in df[~df.ticker.eq('SPY')].groupby('ticker', sort=True):
        block = block.sort_values('session_date').copy()
        dates = pd.DatetimeIndex(pd.to_datetime(block.session_date))
        close = pd.Series(block.adjusted_close.to_numpy(),index=dates).reindex(sessions)
        if (close.dropna() <= 0).any() or not np.isfinite(close.dropna()).all():
            raise ValueError(f'{ticker}: invalid adjusted close')
        returns = close.pct_change(fill_method=None)
        vol = future_volatility(returns,horizon)
        ret = future_return(close,horizon)
        excess_ret = ret - spy_future_returns
        block[TARGETS[0]] = vol.reindex(dates).to_numpy()
        block[TARGETS[2]] = ret.reindex(dates).to_numpy()
        block[TARGETS[4]] = excess_ret.reindex(dates).to_numpy()
        block['target_window_end'] = label_end_map.reindex(dates).dt.strftime('%Y-%m-%d').to_numpy()
        block['spy_return'] = spy_returns.reindex(dates).to_numpy()
        parts.append(block)
    model = pd.concat(parts,ignore_index=True).sort_values(['ticker','session_date']).reset_index(drop=True)
    dates = pd.to_datetime(model.session_date)
    label_ends = pd.to_datetime(model.target_window_end)
    model['dataset_split'] = np.select([dates.lt(validation_start),dates.lt(test_start)], ['train','validation'],default='test')
    # Remove boundary rows from fitting/evaluation when their labels touch the next split.
    purge = (model.dataset_split.eq('train') & label_ends.ge(validation_start)) | (model.dataset_split.eq('validation') & label_ends.ge(test_start))
    model.loc[purge,'dataset_split'] = 'purged'
    missing = model[TARGETS[0]].isna() | model[TARGETS[2]].isna() | model[TARGETS[4]].isna()
    model.loc[missing,'dataset_split'] = 'unlabeled'

    # Compute risk class tertiles strictly on train split
    training_risk = model.loc[model.dataset_split.eq('train'),TARGETS[0]]
    if len(training_risk) < 30:
        raise ValueError('Insufficient labeled training rows.')
    risk_low, risk_high = training_risk.quantile([1/3,2/3]).to_numpy()
    if not np.isfinite([risk_low,risk_high]).all() or risk_low >= risk_high:
        raise ValueError('Training risk tertiles do not define distinct class boundaries.')
    model[TARGETS[1]] = classify(model[TARGETS[0]],float(risk_low),float(risk_high))

    # Compute return class tertiles strictly on train split
    training_ret = model.loc[model.dataset_split.eq('train'),TARGETS[2]]
    ret_low, ret_high = training_ret.quantile([1/3,2/3]).to_numpy()
    if not np.isfinite([ret_low,ret_high]).all() or ret_low >= ret_high:
        raise ValueError('Training return tertiles do not define distinct class boundaries.')
    model[TARGETS[3]] = classify(model[TARGETS[2]],float(ret_low),float(ret_high))

    # Compute excess return (Alpha vs SPY) class tertiles strictly on train split
    training_excess = model.loc[model.dataset_split.eq('train'),TARGETS[4]]
    excess_low, excess_high = training_excess.quantile([1/3,2/3]).to_numpy()
    if not np.isfinite([excess_low,excess_high]).all() or excess_low >= excess_high:
        raise ValueError('Training excess return tertiles do not define distinct class boundaries.')
    model[TARGETS[5]] = classify(model[TARGETS[4]],float(excess_low),float(excess_high))

    if output_dir is None:
        root = prices_path.parents[3]
        output_dir = (root/'data/processed/model_inputs/legacy_runs'/
                      datetime.now(timezone.utc).strftime('legacy_targets_%Y-%m-%dT%H%M%SZ'))
    out = Path(output_dir).resolve()
    out.mkdir(parents=True,exist_ok=False)
    destination = out/'model_dataset.csv'
    model.to_csv(destination,index=False)
    metadata = dict(output_csv=str(destination),source_csv=str(prices_path),
        source_sha256=hashlib.sha256(prices_path.read_bytes()).hexdigest(),
        target_columns=TARGETS,feature_columns=FEATURES,
        decision_time='After session t closes; features use data through t.',
        volatility_definition='sample_std(simple adjusted returns t+1 through t+20, ddof=1) * sqrt(252)',
        return_definition='P[t+20] / P[t] - 1; simple 20-session adjusted close change.',
        excess_return_definition='(P[t+20]/P[t] - 1) - (SPY[t+20]/SPY[t] - 1); 20-session excess return over market benchmark.',
        units='Risk: Annualized decimal volatility. Return & Excess Return: 20-session decimal return.',
        classification_definition='Pooled company training-row tertiles, fixed for validation/test.',
        class_boundaries=dict(
            risk=dict(low_upper_inclusive=float(risk_low),medium_upper_inclusive=float(risk_high)),
            return_=dict(low_upper_inclusive=float(ret_low),medium_upper_inclusive=float(ret_high)),
            excess_return=dict(low_upper_inclusive=float(excess_low),medium_upper_inclusive=float(excess_high))
        ),
        validation_start=validation_start.strftime('%Y-%m-%d'),test_start=test_start.strftime('%Y-%m-%d'),
        split_definition='Shared XNYS sessions: first 70 percent train, next 15 percent validation, final 15 percent test; purge labels crossing boundaries.',
        rows=len(model),companies=int(model.ticker.nunique()),
        split_counts={str(k):int(v) for k,v in model.dataset_split.value_counts().items()},
        class_counts=dict(
            risk={str(k):int(v) for k,v in model[TARGETS[1]].dropna().value_counts().items()},
            return_={str(k):int(v) for k,v in model[TARGETS[3]].dropna().value_counts().items()},
            excess_return={str(k):int(v) for k,v in model[TARGETS[5]].dropna().value_counts().items()}
        ),
        unlabeled_rows=int(missing.sum()),purged_rows=int(purge.sum()),
        excluded_from_features=TARGETS+['target_window_end','dataset_split','source_row','dataset_version','ticker','session_date'],
        notes=['All targets must be excluded from X for every model.',
               'Purged and unlabeled rows must not enter model fitting or evaluation.',
               'SPY is excluded as a modeled stock and supplies a contemporaneous benchmark feature.',
               'No SEC features joined; this is the price-based modeling table.',
               'Source corporate-action and identity verification remains unresolved; core_ready is unchanged.',
               'The risk target is future price volatility, not a Shariah-compliance score.',
               'The return target is 20-session forward price return.',
               'The excess return target isolates stock-specific alpha over SPY, removing broad market trend noise.'])
    # Independently verify numeric labels on first/middle/last eligible rows per issuer.
    for ticker, block in model.groupby('ticker'):
        source = df[df.ticker.eq(ticker)].copy()
        source.index = pd.to_datetime(source.session_date)
        daily = source.adjusted_close.reindex(sessions).pct_change(fill_method=None)
        close_series = source.adjusted_close.reindex(sessions)
        eligible = block[block[TARGETS[0]].notna() & block[TARGETS[2]].notna()]
        for ix in sorted(set([0,len(eligible)//2,len(eligible)-1])):
            if ix < 0:
                continue
            row = eligible.iloc[ix]
            pos = sessions.get_loc(pd.Timestamp(row.session_date))
            window = daily.iloc[pos+1:pos+horizon+1].to_numpy()
            assert len(window)==horizon and np.isfinite(window).all()
            assert np.isclose(row[TARGETS[0]],np.std(window,ddof=1)*np.sqrt(252),rtol=1e-9,atol=1e-12)
            # Verify 20d return
            expected_ret = close_series.iloc[pos+horizon] / close_series.iloc[pos] - 1
            assert np.isclose(row[TARGETS[2]], expected_ret, rtol=1e-9, atol=1e-12)
    assert model[TARGETS[0]].isna().equals(model[TARGETS[1]].isna())
    assert model[TARGETS[2]].isna().equals(model[TARGETS[3]].isna())
    assert model[TARGETS[4]].isna().equals(model[TARGETS[5]].isna())
    assert model[TARGETS[0]].isna().equals(model[TARGETS[4]].isna())
    assert not set(TARGETS).intersection(FEATURES)
    assert model.loc[model.dataset_split.eq('train'),'target_window_end'].lt(validation_start.strftime('%Y-%m-%d')).all()
    assert model.loc[model.dataset_split.eq('validation'),'target_window_end'].lt(test_start.strftime('%Y-%m-%d')).all()
    saved = pd.read_csv(destination)
    assert len(saved)==len(model) and set(TARGETS).issubset(saved.columns)
    metadata['output_sha256'] = hashlib.sha256(destination.read_bytes()).hexdigest()
    metadata['verification'] = 'Passed independent forward-window calculations, split isolation, feature exclusion and CSV readback.'
    (out/'targets_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    (out/'README.md').write_text('''# One table, six targets (Risk, Absolute Return, and Excess Return Alpha)

Use model_dataset.csv for risk, nominal return, and excess return (alpha) regression and classification. All six targets and all future-window metadata are excluded from feature_columns in targets_metadata.json. Select the desired target as y; never include any target in X. Use dataset_split to select train, validation and test rows. Exclude purged and unlabeled rows. Null targets mean insufficient complete future returns.

Targets:
1. risk_volatility_next_20d: Annualized next-20-session realized volatility (regression).
2. risk_class_next_20d: Low/medium/high realized volatility (classification).
3. return_next_20d: Next-20-session price return P[t+20]/P[t] - 1 (regression).
4. return_class_next_20d: Low/medium/high price return (classification).
5. excess_return_next_20d: Next-20-session excess return over SPY benchmark (regression, alpha).
6. excess_return_class_next_20d: Low/medium/high excess return relative to market (classification, alpha).

Classes use training-only pooled tertiles with fixed thresholds. SPY is a benchmark feature, not a modeled company. Targets use future data intentionally; features must not. Rows assume prediction after the current close. The source's unresolved corporate-action and historical identity checks remain applicable.
''',encoding='utf-8')
    print(json.dumps(metadata,indent=2))
    return destination

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    args = parser.parse_args()
    build_targets(args.prices,args.output_dir)
