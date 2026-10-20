"""A registered completed snapshot must remain immutable on reuse."""
import hashlib
import json
import sys

from src.data.collect_screening_fields import main


def test_completed_api_collection_is_reused_without_metadata_rewrite(tmp_path,monkeypatch):
    companies=[dict(ticker=f'SYNTHETIC{i}',cik=str(i)) for i in range(50)]
    report=tmp_path/'reports/screening/ftse_yasaar_2025'
    report.mkdir(parents=True)
    (report/'results.json').write_text(json.dumps(dict(companies=companies)))
    out=tmp_path/'data/raw/synthetic_api';out.mkdir(parents=True)
    payload=b'{"fixture_only":true}'
    files={}
    for c in companies:
        (out/(c['ticker']+'_companyfacts.json')).write_bytes(payload)
        files[c['ticker']]=dict(cik=c['cik'],status='downloaded',sha256=hashlib.sha256(payload).hexdigest())
    metadata=json.dumps(dict(status='complete',downloaded=50,files=files)).encode()
    (out/'metadata.json').write_bytes(metadata)
    monkeypatch.setattr(sys,'argv',['collect','--repo',str(tmp_path),'--out',str(out)])
    def refuse_network(*args,**kwargs):
        raise AssertionError('A completed snapshot must not be downloaded again')
    monkeypatch.setattr('urllib.request.urlopen',refuse_network)
    main()
    assert (out/'metadata.json').read_bytes()==metadata
