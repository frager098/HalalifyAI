"""Check time windows, source flags and benchmark gaps before model fitting."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.features.core import FEATURES,build_features,wilder_rsi
from src.labels.targets import build_targets
from src.data.build_price_research import build_table
from src.data.training_inputs import require_audited_prices


def fixture(n=180):
    sessions=pd.bdate_range('2018-01-02',periods=n)
    rows=[]
    for ticker,rate in [('AAPL',.003),('SPY',.001)]:
        for i,day in enumerate(sessions):
            price=100*np.exp(rate*i+.02*np.sin(i/4))
            rows.append(dict(ticker=ticker,session_date=day,close=price,adjusted_close=price,
                volume=100+i,dataset_version='fixture',share_basis_verified=True,return_transition_verified=i>0))
    return pd.DataFrame(rows),sessions


def test_missing_action_flags_cannot_be_replaced_by_small_price_moves():
    prices,_=fixture()
    prices=prices.drop(columns=['return_transition_verified','share_basis_verified'])
    prices['large_return_review']=False
    prices['zero_volume_review']=False
    with pytest.raises(ValueError,match='Unaudited'):
        require_audited_prices(prices)


def test_complete_past_windows_and_future_prices_do_not_change_past_features():
    prices,dates=fixture()
    before=build_features(prices,dates)
    assert not before.loc[59,'features_ready'] and before.loc[60,'features_ready']
    prices.loc[prices.session_date>=dates[120],'adjusted_close']*=2
    after=build_features(prices,dates)
    pd.testing.assert_frame_equal(before.loc[:119,FEATURES],after.loc[:119,FEATURES])


def test_rsi_seed_and_action_gap_reset():
    price=pd.Series(np.r_[np.arange(100.,115.),112.])
    valid=pd.Series([False]+[True]*15)
    rsi=wilder_rsi(price,valid)
    assert np.isnan(rsi.iloc[13]) and rsi.iloc[14]==100
    assert rsi.iloc[15]==pytest.approx(100-100/(1+13/2))
    valid.iloc[14]=False
    assert wilder_rsi(price,valid).iloc[14:].isna().all()


def test_excess_return_uses_same_future_sessions_and_no_future_benchmark_gap():
    prices,dates=fixture()
    frame,_=build_table(prices,dates)
    i=70
    a=prices[prices.ticker.eq('AAPL')].adjusted_close.to_numpy()
    b=prices[prices.ticker.eq('SPY')].adjusted_close.to_numpy()
    assert frame.loc[i,'future_excess_return_20d']==pytest.approx(a[i+20]/a[i]-b[i+20]/b[i])
    prices.loc[prices.ticker.eq('SPY') & prices.session_date.eq(dates[80]),'return_transition_verified']=False
    after,_=build_table(prices,dates)
    assert not after.loc[i,'labels_ready'] and after.loc[i,'split']=='excluded'


def test_unresolved_stock_action_blocks_entire_future_target_window():
    prices,dates=fixture()
    prices.loc[prices.ticker.eq('AAPL') & prices.session_date.eq(dates[80]),'return_transition_verified']=False
    frame=build_targets(prices,dates)
    assert not frame.loc[60:79,'labels_ready'].any()
    assert not frame.tail(20).labels_ready.any()


def test_notebook_rejects_wrong_csv_before_feature_creation():
    path=Path(__file__).parents[1]/'notebooks/HalalifyAI_Colab_Risk_Return.ipynb'
    notebook=json.loads(path.read_text(encoding='utf8'))
    for cell in notebook['cells']:
        if cell['cell_type']=='code':
            compile(''.join(cell['source']),str(path),'exec')
    scope=dict(DATASET_SHA='wrong',EXPECTED_PRICE_CSV_SHA256='registered')
    with pytest.raises(ValueError,match='Unregistered'):
        exec(''.join(notebook['cells'][12]['source']),scope)
