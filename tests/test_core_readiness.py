import numpy as np
import pandas as pd
import pytest
from src.data.check_price_actions import audit
from src.features.core import FEATURES,build_features,wilder_rsi
from src.labels.targets import build_targets,split_and_label
from src.models.train_candidates import metrics


def fixture(n=100):
    dates=pd.bdate_range('2016-01-04',periods=n)
    market=np.r_[100,100*np.cumprod(1+np.resize([.01,-.005,.003],n-1))]
    rows=[]
    for ticker,p in [('SPY',market),('AAPL',np.full(n,100.))]:
        for i,date in enumerate(dates):
            rows.append(dict(ticker=ticker,session_date=str(date.date()),close=p[i],adjusted_close=p[i],volume=100.,
                dataset_version='test',share_basis_verified=True,return_transition_verified=i>0))
    return pd.DataFrame(rows),dates


def test_constant_stock_and_exact_window():
    prices,dates=fixture();f=build_features(prices,dates)
    assert not f.loc[59,'features_ready']
    assert f.loc[60,'features_ready']
    assert f.loc[60,'rsi_14']==50
    assert f.loc[60,'max_drawdown_60d']==0
    assert f.loc[60,'vol_20d']==0
    assert f.loc[60,'beta_60d']==pytest.approx(0)
    assert f.loc[60,'log_dollar_volume_20d']==pytest.approx(np.log1p(10000))


def test_wilder_seed_and_recursive_update():
    p=pd.Series(np.r_[np.arange(100.,115.),112.])
    rsi=wilder_rsi(p,pd.Series([False]+[True]*15))
    assert np.isnan(rsi.iloc[13])
    assert rsi.iloc[14]==100
    assert rsi.iloc[15]==pytest.approx(100-100/(1+13/2))


def test_gap_resets_rsi_and_complete_feature_window():
    prices,dates=fixture(150)
    prices=prices[~((prices.ticker=='AAPL')&(prices.session_date==str(dates[70].date())))]
    f=build_features(prices,dates)
    assert not f.loc[130,'features_ready']
    assert f.loc[131,'features_ready']


def test_changing_future_prices_does_not_change_past_features():
    prices,dates=fixture();before=build_features(prices,dates)
    prices.loc[prices.session_date>=str(dates[80].date()),'adjusted_close']*=2
    after=build_features(prices,dates)
    pd.testing.assert_frame_equal(before.loc[:79,FEATURES],after.loc[:79,FEATURES])


def test_known_future_return_and_final_20_sessions():
    prices,dates=fixture()
    mask=prices.ticker=='AAPL';prices.loc[mask,'adjusted_close']=100*1.08**(np.arange(100)/20)
    y=build_targets(prices,dates)
    assert y.loc[0,'future_return_20d']==pytest.approx(.08)
    assert y.loc[0,'label_end_date']==dates[20]
    assert not y.tail(20).labels_ready.any()


def test_unresolved_transition_blocks_future_target():
    prices,dates=fixture()
    prices.loc[(prices.ticker=='AAPL')&(prices.session_date==str(dates[15].date())),'return_transition_verified']=False
    y=build_targets(prices,dates)
    assert not y.loc[0,'labels_ready']


def test_training_only_thresholds_and_label_purge():
    dates=pd.to_datetime(['2018-01-02','2019-01-02','2020-12-15','2021-01-04','2022-12-15','2023-01-03'])
    ends=pd.to_datetime(['2018-01-30','2019-01-30','2021-01-15','2021-02-01','2023-01-15','2023-01-31'])
    f=pd.DataFrame(dict(as_of_date=dates,label_end_date=ends,features_ready=True,labels_ready=True,
        future_return_20d=[-.1,.1,.9,.4,.9,.7],future_volatility_20d=[.1,.3,.9,.4,.9,.7],exclusion_reason=''))
    a,c=split_and_label(f)
    assert a.loc[2,'split']=='excluded' and a.loc[4,'split']=='excluded'
    f.loc[3:,'future_return_20d']=100
    assert split_and_label(f)[1]['future_return_20d']==c['future_return_20d']


def test_split_basis_rounding_and_mismatch():
    prices=pd.DataFrame(dict(ticker=['AAPL','AAPL'],session_date=['2020-08-28','2020-08-31'],
        close=[25.,25.],adjusted_close=[25.,25.],volume=[400,100]))
    raw=pd.DataFrame(dict(ticker=['AAPL','AAPL'],session_date=prices.session_date,
        raw_close=[100.,25.],raw_volume=[100,100]))
    f,_=audit(prices,raw,[])
    assert f.share_basis_verified.all()
    assert not f.loc[1,'return_transition_verified']
    split=('forward_splits',dict(symbol='AAPL',ex_date='2020-08-31',new_rate=4,old_rate=1))
    assert audit(prices,raw,[split])[0].loc[1,'return_transition_verified']
    prices.loc[0,'volume']=500
    assert not audit(prices,raw,[])[0].loc[0,'share_basis_verified']


def test_dividend_ratio_and_unknown_spinoff():
    p=pd.DataFrame(dict(ticker=['AAPL','AAPL'],session_date=['2016-02-03','2016-02-04'],
        close=[100.,98.],adjusted_close=[98.,98.],volume=[100,100]))
    raw=p[['ticker','session_date','close','volume']].rename(columns={'close':'raw_close','volume':'raw_volume'})
    dividend=('cash_dividends',dict(symbol='AAPL',ex_date='2016-02-04',rate=2))
    assert audit(p,raw,[dividend])[0].loc[1,'return_transition_verified']
    spin=('spin_offs',dict(source_symbol='AAPL',ex_date='2016-02-04'))
    assert not audit(p,raw,[spin])[0].loc[1,'return_transition_verified']


def test_log_loss_column_order():
    p=np.array([[.98,.01,.01],[.01,.98,.01],[.01,.01,.98]])
    result=metrics(['low','medium','high'],['low','medium','high'],p)
    assert result['log_loss']==pytest.approx(-np.log(.98))


def test_screening_handoff_keeps_future_evidence_out_and_never_passes_unknowns():
    from src.data.prepare_screening_handoff import handoff
    facts=pd.DataFrame([
        dict(ticker='AAPL',metric_name='total_assets',source_tag='Assets',
             period_start=None,period_end='2025-09-30',available_from_session='2025-11-03',fact_id='known',value=10),
        dict(ticker='AAPL',metric_name='total_assets',source_tag='Assets',
             period_start=None,period_end='2025-12-31',available_from_session='2026-02-02',fact_id='future',value=20)])
    packs=handoff(facts,'2025-12-31')
    assert len(packs)==50 and not any(p['portfolio_eligible'] for p in packs)
    assert all(v is None for p in packs for v in p['approved_metrics'].values())
    apple=next(p for p in packs if p['ticker']=='AAPL')
    assert [x['fact_id'] for x in apple['evidence_candidates']['total_assets']]==['known']
