"""The dictionary's 16 core features with complete session/quality windows."""
import numpy as np
import pandas as pd

FEATURES = ['ret_1d','ret_5d','ret_20d','ret_60d','vol_20d','vol_60d',
    'downside_dev_20d','max_drawdown_60d','price_sma20_ratio','price_sma50_ratio',
    'rsi_14','volume_ratio_20d','log_dollar_volume_20d','beta_60d',
    'market_ret_20d','market_vol_20d']


def wilder_rsi(price, transition):
    result = np.full(len(price), np.nan)
    gain_sum = loss_sum = 0.0
    average_gain = average_loss = None
    count = 0
    for i in range(1,len(price)):
        if not transition.iloc[i] or not np.isfinite(price.iloc[i-1:i+1]).all():
            gain_sum = loss_sum = 0.; average_gain = average_loss = None; count = 0
            continue
        delta = price.iloc[i]-price.iloc[i-1]
        gain, loss = max(delta,0), max(-delta,0)
        if average_gain is None:
            gain_sum += gain; loss_sum += loss; count += 1
            if count < 14: continue
            average_gain, average_loss = gain_sum/14, loss_sum/14
        else:
            average_gain = (13*average_gain+gain)/14
            average_loss = (13*average_loss+loss)/14
        result[i] = (50. if average_gain == average_loss == 0 else
            100. if average_loss == 0 else 0. if average_gain == 0 else
            100-100/(1+average_gain/average_loss))
    return pd.Series(result,index=price.index)


def build_features(prices, calendar):
    if prices.duplicated(['ticker','session_date']).any():
        raise ValueError('Duplicate instrument/session')
    prices = prices.copy()
    prices['session_date'] = pd.to_datetime(prices.session_date)
    if not prices.session_date.isin(calendar).all():
        raise ValueError('Unexpected exchange session')
    groups = {ticker: group.set_index('session_date').reindex(calendar)
              for ticker,group in prices.groupby('ticker')}
    if 'SPY' not in groups: raise ValueError('SPY is required')
    spy = groups['SPY']
    market = spy.adjusted_close.pct_change(fill_method=None).where(
        spy.return_transition_verified.fillna(False))
    output=[]
    for ticker, group in groups.items():
        if ticker == 'SPY': continue
        p=group.adjusted_close
        transition=group.return_transition_verified.fillna(False).astype(bool)
        basis=group.share_basis_verified.fillna(False).astype(bool)
        r=p.pct_change(fill_method=None).where(transition)
        features=pd.DataFrame(index=calendar)
        for k in [1,5,20,60]:features[f'ret_{k}d']=p/p.shift(k)-1
        for k in [20,60]:features[f'vol_{k}d']=r.rolling(k,min_periods=k).std(ddof=1)*np.sqrt(252)
        features['downside_dev_20d']=np.sqrt(r.clip(upper=0).pow(2).rolling(20,min_periods=20).mean())*np.sqrt(252)
        features['max_drawdown_60d']=p.rolling(61,min_periods=61).apply(
            lambda a:np.max(1-a/np.maximum.accumulate(a)),raw=True)
        for k in [20,50]:features[f'price_sma{k}_ratio']=p/p.rolling(k,min_periods=k).mean()-1
        features['rsi_14']=wilder_rsi(p,transition)
        volume=group.volume.where(basis)
        features['volume_ratio_20d']=volume/volume.rolling(20,min_periods=20).mean().replace(0,np.nan)
        features['log_dollar_volume_20d']=np.log1p((group.close*volume).rolling(20,min_periods=20).mean())
        features['beta_60d']=r.rolling(60,min_periods=60).cov(market,ddof=1)/market.rolling(60,min_periods=60).var(ddof=1).replace(0,np.nan)
        features['market_ret_20d']=spy.adjusted_close/spy.adjusted_close.shift(20)-1
        features['market_vol_20d']=market.rolling(20,min_periods=20).std(ddof=1)*np.sqrt(252)
        valid=(transition.astype(int).rolling(60,min_periods=60).sum().eq(60)
               &market.notna().astype(int).rolling(60,min_periods=60).sum().eq(60)
               &basis.astype(int).rolling(20,min_periods=20).sum().eq(20))
        ready=valid & np.isfinite(features[FEATURES]).all(axis=1)
        features.loc[~ready,FEATURES]=np.nan
        features['features_ready']=ready
        features['unavailable_reasons']=np.where(ready,'','incomplete_window_or_unresolved_action_or_basis')
        features['ticker']=ticker
        features['instrument_id']='US_'+ticker
        versions=group.dataset_version.dropna().unique()
        if len(versions)!=1:raise ValueError('Mixed input dataset versions')
        features['dataset_version']=versions[0]
        features['feature_set_version']='core_v1'
        features['cutoff_policy']='historical_after_close_assumed_bar_arrival_unrecorded'
        features.index.name='as_of_date'
        output.append(features.reset_index())
    return pd.concat(output,ignore_index=True)
