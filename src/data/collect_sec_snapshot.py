"""Preserve fresh SEC responses in a versioned folder, including historical XOM issuer.

Run: python -m src.data.collect_sec_snapshot --symbols XOM --user-agent "Project contact@email"
For this fixed 2016-2025 experiment XOM uses predecessor CIK 0000034088.
This is NOT a general automatic merger-history mapping.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import time
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .reconciliation import COMPANY_SYMBOLS, run_id, save_json, sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--symbols', nargs='+', default=COMPANY_SYMBOLS)
    p.add_argument('--user-agent', default=None)
    args = p.parse_args()
    load_dotenv(args.repo / '.env')
    agent = args.user_agent or os.getenv('SEC_USER_AGENT')
    if not agent or '@' not in agent:
        p.error('Supply SEC_USER_AGENT identifying your project and real contact email.')
    folder = args.repo / 'data/raw/sec_snapshots' / run_id()
    folder.mkdir(parents=True, exist_ok=False)
    metadata = dict(provider='SEC EDGAR', scope='2016-2025 study issuer mapping',
                    retrieved_at=datetime.now(timezone.utc).isoformat(), files=[], failed=[],
                    identity_verified=False,
                    xom_mapping_source='https://www.sec.gov/Archives/edgar/data/34088/000119312526291986/d70995d8k.htm')
    with requests.Session() as http:
        http.headers.update({'User-Agent': agent, 'Accept-Encoding': 'gzip, deflate'})
        http.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,
            status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])))
        try:
            response=http.get('https://www.sec.gov/files/company_tickers.json',timeout=60)
            response.raise_for_status()
            mapping_path=folder/'company_tickers.json'; mapping_path.write_bytes(response.content)
            mapping={item['ticker']:str(item['cik_str']).zfill(10) for item in response.json().values()}
            metadata['ticker_mapping_sha256']=sha256(mapping_path)
            for ticker in args.symbols:
                cik='0000034088' if ticker=='XOM' else mapping.get(ticker)
                if not cik:
                    metadata['failed'].append(dict(ticker=ticker,reason='No CIK in current mapping')); continue
                for kind,url,name in [
                    ('companyfacts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',f'{ticker}_companyfacts.json'),
                    ('submissions',f'https://data.sec.gov/submissions/CIK{cik}.json',f'{ticker}_submissions.json')]:
                    try:
                        print(f'Downloading {ticker} {kind} CIK {cik}...',flush=True)
                        response=http.get(url,timeout=60); response.raise_for_status()
                        payload=response.json()
                        if int(payload['cik']) != int(cik):
                            raise ValueError('SEC response CIK differs from requested issuer.')
                        path=folder/name; path.write_bytes(response.content)
                        metadata['files'].append(dict(ticker=ticker,cik=cik,kind=kind,url=url,
                            file=name,sha256=sha256(path),entity_name=payload.get('entityName',payload.get('name'))))
                    except (requests.RequestException,ValueError,KeyError) as error:
                        metadata['failed'].append(dict(ticker=ticker,kind=kind,reason=str(error)))
                    time.sleep(.25)
            metadata['status']='downloaded_requires_identity_review' if not metadata['failed'] else 'incomplete'
        finally:
            save_json(folder/'metadata.json',metadata)
    print(f'Saved snapshot: {folder}')
    if metadata['failed']:
        raise SystemExit('Some SEC requests failed; inspect metadata.json. Do not assume complete coverage.')


if __name__=='__main__':
    main()
