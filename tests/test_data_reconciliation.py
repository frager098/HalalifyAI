import json
from pathlib import Path
import pandas as pd
import pytest

from src.data.collect_price_bases import combine_bases, parse_bars, collect
from src.data.prepare_sec import classify_facts, extract
from src.data.validate_data import sessions
from src.data.reconciliation import COMPANY_SYMBOLS


def test_documented_universe_matches_collection():
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'configs/universe.json').read_text())
    assert config['company_symbols']==COMPANY_SYMBOLS
    assert len(set(COMPANY_SYMBOLS))==50 and 'SPY' not in COMPANY_SYMBOLS
    assert config['benchmark_symbols']==['SPY']


def prices(close=100, volume=1000):
    return pd.DataFrame([dict(ticker='SPY', session_date='2020-01-02',
        open=close, high=close+1, low=close-1, close=close, volume=volume)])


def test_price_bases_keep_dividend_adjusted_close_separate():
    result = combine_bases(prices(100), prices(98), 'test')
    assert result.iloc[0]['close'] == 100
    assert result.iloc[0]['adjusted_close'] == 98
    assert result.iloc[0]['close'] * result.iloc[0]['volume'] == 100000
    assert not result.iloc[0]['adjustment_verified']
    assert pd.isna(result.iloc[0]['dividend_per_share'])


def test_mismatched_series_fail_instead_of_dropping_session():
    other = prices()
    other.loc[0, 'session_date'] = '2020-01-03'
    with pytest.raises(ValueError, match='different session keys'):
        combine_bases(prices(), other, 'test')


def test_exchange_date_uses_timezone_not_utc_date():
    bars = {'bars': {'SPY': [dict(t='2020-01-03T01:00:00Z',o=1,h=2,l=1,c=2,v=3)]}}
    assert parse_bars(bars)[0]['session_date'] == '2020-01-02'


def test_duplicate_prices_rejected():
    duplicate = pd.concat([prices(), prices()])
    with pytest.raises(ValueError, match='Duplicate'):
        combine_bases(duplicate, prices(), 'test')


def facts(value=100, end='2020-03-31', filed='2020-05-01', metric='debt_component', unit='USD'):
    return pd.DataFrame([dict(fact_id='a', ticker='AAPL',source_tag='DebtCurrent',unit=unit,
        metric_name=metric,value=value,period_start=None,period_end=end,filed_date=filed,
        accession_number='one',frame=None)])


def test_filing_available_only_next_session_even_when_friday():
    usable, rejected, _ = classify_facts(facts(), sessions('2020-01-01','2020-12-31'))
    assert len(rejected) == 0
    assert usable.iloc[0]['available_from_session'] == '2020-05-04'


@pytest.mark.parametrize('data,reason', [
    (facts(value=-1),'negative_amount'),
    (facts(end='2020-06-01'),'period_after_filing'),
    (facts(unit='EUR'),'non_usd')])
def test_bad_financial_facts_quarantined_not_corrected(data, reason):
    usable, rejected, _ = classify_facts(data, sessions('2020-01-01','2020-12-31'))
    assert usable.empty
    assert reason in rejected.iloc[0]['quarantine_reason']
    assert rejected.iloc[0]['value'] == data.iloc[0]['value']


def test_negative_net_income_valid_with_duration():
    data = facts(value=-10, metric='net_income_candidate')
    data['period_start'] = '2020-01-01'
    usable, rejected, _ = classify_facts(data, sessions('2020-01-01','2020-12-31'))
    assert len(usable) == 1 and rejected.empty


def test_filing_versions_not_collapsed():
    first = facts()
    later = facts(value=110,filed='2020-05-05')
    later['fact_id'] = 'b'; later['accession_number'] = 'two'
    usable, rejected, duplicates = classify_facts(pd.concat([first,later],ignore_index=True),
        sessions('2020-01-01','2020-12-31'))
    assert len(usable) == 2 and rejected.empty and duplicates == 0


def test_same_filing_conflict_is_quarantined():
    first, second = facts(), facts(value=110)
    second['fact_id'] = 'b'
    usable, rejected, _ = classify_facts(pd.concat([first,second],ignore_index=True),
        sessions('2020-01-01','2020-12-31'))
    assert usable.empty and len(rejected) == 2


def test_amendments_and_source_identity_preserved(tmp_path):
    item = dict(val=100,end='2020-03-31',filed='2020-05-01',form='10-Q/A',accn='0000320193-20-000001')
    path = tmp_path/'AAPL_companyfacts.json'
    path.write_text(json.dumps(dict(cik=320193,entityName='Apple',facts={'us-gaap':{
        'Assets':{'units':{'USD':[item]}}}})),encoding='utf-8')
    rows = extract(path)
    assert len(rows)==1 and rows[0]['is_amendment']
    assert rows[0]['cik']=='0000320193' and rows[0]['review_status']=='unreviewed'


def test_collection_paginates_and_preserves_old_files(tmp_path):
    old = tmp_path/'data/raw/alpaca_historical_prices.csv'
    old.parent.mkdir(parents=True); old.write_text('old snapshot')
    class Response:
        status_code=200
        def __init__(self,date,token):
            self.payload={'bars':{'SPY':[dict(t=date+'T05:00:00Z',o=100,h=101,l=99,c=100,v=1000)]},'next_page_token':token}
            self.content=json.dumps(self.payload).encode()
        def json(self): return self.payload
    class HTTP:
        def get(self,url,params,timeout):
            return Response('2020-01-03',None) if params.get('page_token') else Response('2020-01-02','next')
    path=collect(tmp_path,['SPY'],'2020-01-01','2020-01-03',HTTP())
    assert len(pd.read_csv(path))==2
    assert old.read_text()=='old snapshot'
    assert len(list((tmp_path/'data/raw/alpaca').rglob('split_*.json')))==2
