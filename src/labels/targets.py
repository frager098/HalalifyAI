import numpy as np
import pandas as pd


def build_targets(prices,calendar,horizon=20):
    output=[]
    if horizon!=20:raise ValueError('This registered experiment uses a 20-session horizon')
    for ticker,g in prices.groupby('ticker'):
        if ticker=='SPY':continue
        g=g.copy();g['session_date']=pd.to_datetime(g.session_date)
        g=g.set_index('session_date').reindex(calendar)
        p=g.adjusted_close
        r=p.pct_change(fill_method=None).where(g.return_transition_verified.fillna(False))
        future_return=p.shift(-horizon)/p-1
        future_vol=r.rolling(horizon,min_periods=horizon).std(ddof=1).shift(-horizon)*np.sqrt(252)
        good=r.notna().astype(int).rolling(horizon,min_periods=horizon).sum().shift(-horizon).eq(horizon)
        ready=good & np.isfinite(future_return) & np.isfinite(future_vol)
        dates=pd.Series(calendar,index=calendar)
        out=pd.DataFrame(dict(ticker=ticker,as_of_date=calendar,
            label_start_date=dates.shift(-1).values,label_end_date=dates.shift(-horizon).values,
            future_return_20d=future_return.where(ready).values,
            future_volatility_20d=future_vol.where(ready).values,labels_ready=ready.values))
        out['exclusion_reason']=np.where(ready,'','future_not_observed_or_gap_or_unresolved_action')
        out['label_version']='core_20d_readiness_v1'
        out['horizon_sessions']=horizon
        output.append(out)
    return pd.concat(output,ignore_index=True)


def split_and_label(frame):
    f=frame.copy()
    if 'exclusion_reason' not in f:
        f['exclusion_reason']=''
    # A valid future target does not imply a valid past feature window.
    # Keep the feature reason rather than reporting blank exclusions.
    unavailable=~f.features_ready
    reasons=(f['unavailable_reasons'].fillna('incomplete_feature_window')
             if 'unavailable_reasons' in f else pd.Series('incomplete_feature_window',index=f.index))
    existing=f['exclusion_reason'].fillna('')
    f.loc[unavailable,'exclusion_reason']=np.where(
        existing[unavailable].eq(''),reasons[unavailable],
        existing[unavailable]+';'+reasons[unavailable])
    eligible=f.features_ready & f.labels_ready
    f['split']='excluded'
    for name,start,end,next_start in [
        ('train','2016-01-01','2020-12-31','2021-01-01'),
        ('validation','2021-01-01','2022-12-31','2023-01-01'),
        ('test','2023-01-01','2025-12-31',None)]:
        mask=eligible & f.as_of_date.between(pd.Timestamp(start),pd.Timestamp(end))
        if next_start:
            purge=mask & (f.label_end_date>=pd.Timestamp(next_start))
            f.loc[purge,'exclusion_reason']='split_boundary_purge'
            mask &= ~purge
        f.loc[mask,'split']=name
    train=f[f.split=='train']
    if train.empty:raise ValueError('No eligible initial training rows')
    cutoffs={}
    for target,label in [('future_return_20d','return_class'),('future_volatility_20d','risk_class')]:
        lo,hi=train[target].quantile([1/3,2/3],interpolation='linear').tolist()
        if not np.isfinite([lo,hi]).all() or not hi>lo:raise ValueError('Invalid/equal training cutoffs')
        cutoffs[target]=dict(lower_cutoff=lo,upper_cutoff=hi,quantile_method='linear',
            fit_row_count=len(train),fit_feature_date_start=str(train.as_of_date.min().date()),
            fit_feature_date_end=str(train.as_of_date.max().date()),fit_label_end_max=str(train.label_end_date.max().date()),
            class_order=['low','medium','high'],boundary_rule='low<=lower; lower<medium<=upper; high>upper')
        f[label]=None
        used=f.split!='excluded'
        f.loc[used,label]=np.where(f.loc[used,target]<=lo,'low',np.where(f.loc[used,target]<=hi,'medium','high'))
    for before,after in [('train','validation'),('validation','test')]:
        a,b=f[f.split==before],f[f.split==after]
        if not a.empty and not b.empty and not a.label_end_date.max()<b.as_of_date.min():
            raise ValueError('Label boundary leaks into next partition')
    return f,cutoffs
