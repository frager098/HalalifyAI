import hashlib
import json

import pandas as pd
import pytest

from src.data.training_inputs import prepare, require_audited_prices
from src.labels.targets import split_and_label


def prices():
    return pd.DataFrame([
        dict(ticker=ticker, session_date=date, open=100., high=100., low=100.,
             close=100., adjusted_close=100., volume=100., dataset_version='fixture',
             share_basis_verified='true', return_transition_verified=flag)
        for ticker in ['AAPL', 'SPY']
        for date, flag in [('2020-01-02', 'false'), ('2020-01-03', 'true')]
    ])


def test_missing_flags_never_become_verified():
    with pytest.raises(ValueError, match='Unaudited'):
        require_audited_prices(prices().drop(columns=['share_basis_verified']))


def test_false_strings_preserved_and_unknown_rejected():
    result = require_audited_prices(prices())
    assert result.return_transition_verified.tolist() == [False, True, False, True]
    frame = prices()
    frame.loc[0, 'share_basis_verified'] = 'unknown'
    with pytest.raises(ValueError, match='boolean'):
        require_audited_prices(frame)


def test_duplicate_keys_and_missing_benchmark_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        require_audited_prices(pd.concat([prices(), prices().iloc[:1]]))
    with pytest.raises(ValueError, match='SPY'):
        require_audited_prices(prices().query("ticker == 'AAPL'"))


def evidence(tmp_path, status='downloaded_requires_event_review'):
    original = tmp_path / 'daily_prices.csv'
    prices().drop(columns=['share_basis_verified', 'return_transition_verified']).to_csv(original, index=False)
    raw_folder = tmp_path / 'raw'
    raw_folder.mkdir()
    raw = prices()[['ticker', 'session_date', 'close', 'volume']].rename(columns={'close':'raw_close', 'volume':'raw_volume'})
    raw.to_csv(raw_folder / 'raw_prices.csv', index=False)
    actions = tmp_path / 'actions'
    actions.mkdir()
    for folder, payload, state in [(raw_folder, {'bars':{}}, 'downloaded'),
                                   (actions, {'corporate_actions':{}}, status)]:
        page = folder / 'page_0001.json'
        page.write_text(json.dumps(payload))
        metadata = dict(status=state, pages=[dict(file=page.name, sha256=hashlib.sha256(page.read_bytes()).hexdigest())])
        if folder == raw_folder:
            metadata['csv_sha256'] = hashlib.sha256((folder/'raw_prices.csv').read_bytes()).hexdigest()
        (folder/'metadata.json').write_text(json.dumps(metadata))
    return original, raw_folder/'raw_prices.csv', actions


def test_failed_action_download_stops_before_training_output(tmp_path):
    paths = evidence(tmp_path, status='failed')
    with pytest.raises(ValueError, match='Incomplete'):
        prepare(*paths, tmp_path)
    assert not (tmp_path/'data').exists()


def test_routes_to_new_audited_output_and_preserves_source(tmp_path):
    paths = evidence(tmp_path)
    before = paths[0].read_bytes()
    output = prepare(*paths, tmp_path)
    assert output != paths[0] and output.name == 'audited_prices.csv'
    frame = require_audited_prices(pd.read_csv(output))
    assert frame.return_transition_verified.tolist() == [False, True, False, True]
    assert paths[0].read_bytes() == before


def test_reference_tampering_stops_before_training_output(tmp_path):
    paths = evidence(tmp_path)
    with paths[1].open('a') as stream:
        stream.write('\n')
    with pytest.raises(ValueError, match='metadata'):
        prepare(*paths, tmp_path)


def test_unavailable_features_keep_exclusion_reason_even_with_valid_target():
    frame=pd.DataFrame(dict(as_of_date=pd.to_datetime(['2018-01-02','2018-02-01','2018-03-01']),
        label_end_date=pd.to_datetime(['2018-01-30','2018-02-28','2018-03-29']),
        features_ready=[False,True,True],labels_ready=True,
        unavailable_reasons=['unresolved_action','',''],exclusion_reason='',
        future_return_20d=[0.,-.1,.1],future_volatility_20d=[.2,.1,.3]))
    result,_=split_and_label(frame)
    assert result.loc[0,'split']=='excluded'
    assert result.loc[0,'exclusion_reason']=='unresolved_action'
