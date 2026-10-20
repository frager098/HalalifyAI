"""Independently recompute every retained forward target using NumPy windows."""
import argparse
import json
from pathlib import Path
import exchange_calendars as xc
import numpy as np
import pandas as pd
from .reconciliation import sha256, save_json
from .training_inputs import require_audited_prices
from ..features.core import FEATURES


def verify(prices_path, dataset_folder, out):
    folder=Path(dataset_folder)
    metadata=json.loads((folder/'metadata.json').read_text())
    if sha256(prices_path)!=metadata['input_sha256'] or sha256(folder/'research_rows.csv')!=metadata['output_sha256']:
        raise ValueError('Dataset or input changed from recorded manifest')
    prices=require_audited_prices(pd.read_csv(prices_path))
    data=pd.read_csv(folder/'research_rows.csv',parse_dates=['as_of_date','label_start_date','label_end_date'])
    sessions=xc.get_calendar('XNYS',start='2016-01-01',end='2025-12-31').sessions
    if data.duplicated(['ticker','as_of_date']).any() or len(data)!=metadata['eligible_rows']:
        raise ValueError('Duplicate or missing retained observations')
    if not np.isfinite(data[FEATURES+['future_return_20d','future_volatility_20d','future_excess_return_20d']]).all().all():
        raise ValueError('Nonfinite retained values')
    spy=prices[prices.ticker.eq('SPY')].set_index('session_date').reindex(sessions)
    max_errors=dict(future_return_20d=0.,future_volatility_20d=0.,future_excess_return_20d=0.)
    checked=0
    for ticker, block in data.groupby('ticker'):
        source=prices[prices.ticker.eq(ticker)].set_index('session_date').reindex(sessions)
        i=sessions.get_indexer(block.as_of_date)
        if (i<0).any() or (i+20>=len(sessions)).any():raise ValueError('Target outside exchange calendar')
        p=source.adjusted_close.to_numpy()
        market=spy.adjusted_close.to_numpy()
        returns=p[1:]/p[:-1]-1
        windows=np.lib.stride_tricks.sliding_window_view(returns,20)
        expected=dict(future_return_20d=p[i+20]/p[i]-1,
            future_volatility_20d=windows[i].std(axis=1,ddof=1)*np.sqrt(252),
            future_excess_return_20d=p[i+20]/p[i]-market[i+20]/market[i])
        for key, values in expected.items():
            if not np.allclose(values,block[key],atol=1e-11,rtol=1e-11):raise ValueError('Wrong future target: '+key)
            max_errors[key]=max(max_errors[key],float(np.max(np.abs(values-block[key]))))
        for check_source in [source,spy]:
            flags=check_source.return_transition_verified.fillna(False).to_numpy(dtype=bool)
            future_flags=np.lib.stride_tricks.sliding_window_view(flags[1:],20)
            if not future_flags[i].all():raise ValueError('Unverified future action enters a target')
        if not (block.label_start_date.to_numpy()==sessions[i+1].to_numpy()).all():raise ValueError('Label starts on wrong session')
        if not (block.label_end_date.to_numpy()==sessions[i+20].to_numpy()).all():raise ValueError('Label ends on wrong session')
        checked+=len(block)
    for before, after in [('train','validation'),('validation','test')]:
        if not data.loc[data.split.eq(before),'label_end_date'].max()<data.loc[data.split.eq(after),'as_of_date'].min():
            raise ValueError('Forward label leaks across partitions')
    train=data[data.split.eq('train')]
    for target, label in [('future_return_20d','return_class'),('future_volatility_20d','risk_class'),('future_excess_return_20d','excess_return_class')]:
        lo,hi=train[target].quantile([1/3,2/3],interpolation='linear')
        stored=metadata['label_thresholds'][target]
        if not np.allclose([lo,hi],[stored['lower_cutoff'],stored['upper_cutoff']]):raise ValueError('Threshold is not train-only')
        expected=np.where(data[target]<=stored['lower_cutoff'],'low',np.where(data[target]<=stored['upper_cutoff'],'medium','high'))
        if not (data[label]==expected).all():raise ValueError('Class labels do not match frozen thresholds')
    report=dict(rows_independently_checked=checked,companies=int(data.ticker.nunique()),
        max_absolute_target_errors=max_errors,all_targets_recomputed=True,no_future_action_gaps=True,
        chronological_purges_verified=True,training_only_thresholds_verified=True,
        numeric_features_complete=True,global_action_or_issuer_certification=False,model_accuracy_measured=False)
    save_json(out,report)
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices',type=Path,required=True);p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();verify(args.prices,args.dataset,args.out)
