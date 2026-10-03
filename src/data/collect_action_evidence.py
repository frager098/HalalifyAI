"""Save corporate-action responses as evidence; empty results do not prove completeness."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import time
import requests
from dotenv import load_dotenv
from .reconciliation import COMPANY_SYMBOLS, run_id, save_json, sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    args=p.parse_args()
    load_dotenv(args.repo/'.env')
    key,secret=os.getenv('ALPACA_API_KEY'),os.getenv('ALPACA_SECRET_KEY')
    if not key or not secret: p.error('Local Alpaca credentials are required.')
    folder=args.repo/'data/raw/actions'/run_id(); folder.mkdir(parents=True,exist_ok=False)
    url='https://data.alpaca.markets/v1/corporate-actions'
    # Endpoint bounds filter process_date, not ex-date. Fetch through collection
    # date so late processed historical actions are not automatically omitted.
    params=dict(symbols=','.join(COMPANY_SYMBOLS+['SPY']),start='2016-01-01',
        end=datetime.now(timezone.utc).strftime('%Y-%m-%d'),limit=1000,sort='asc',data_quality='all')
    metadata=dict(source_request=dict(endpoint=url,parameters=params.copy()),status='started',
        bound_semantics='process_date; ex-date must be filtered during normalization',
        coverage_verified=False,pages=[])
    tokens=set()
    try:
        with requests.Session() as http:
            http.headers.update({'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
            while True:
                response=http.get(url,params=params,timeout=60)
                if response.status_code!=200:
                    raise RuntimeError(f'Action endpoint HTTP {response.status_code}; do not assume no actions.')
                path=folder/f'page_{len(metadata["pages"])+1:04d}.json';path.write_bytes(response.content)
                metadata['pages'].append(dict(file=path.name,sha256=sha256(path)))
                payload=response.json(); token=payload.get('next_page_token')
                if not token: break
                if token in tokens: raise ValueError('Repeated page token.')
                tokens.add(token);params['page_token']=token;time.sleep(.25)
        metadata['status']='downloaded_requires_event_review'
    except Exception as error:
        metadata.update(status='failed',error=str(error)); raise
    finally:
        save_json(folder/'metadata.json',metadata)
        print(f'Action evidence: {folder}')


if __name__=='__main__': main()
