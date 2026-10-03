"""Download immutable unadjusted SIP bars for comparison with saved split/all bars."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from .reconciliation import save_json, sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    load_dotenv()
    symbols = sorted(pd.read_csv(a.prices, usecols=['ticker']).ticker.unique())
    params = dict(symbols=','.join(symbols), timeframe='1Day',
        start='2016-01-01T00:00:00-05:00', end='2025-12-31T23:59:59-05:00',
        feed='sip', adjustment='raw', currency='USD', asof='2025-12-31', limit=10000, sort='asc')
    a.output.mkdir(parents=True, exist_ok=False)
    metadata = dict(source_request=params.copy(), pages=[], status='collecting',
        started_at_utc=datetime.now(timezone.utc).isoformat())
    rows = []; seen = set()
    with requests.Session() as http:
        http.headers.update({'APCA-API-KEY-ID': os.environ['ALPACA_API_KEY'],
                             'APCA-API-SECRET-KEY': os.environ['ALPACA_SECRET_KEY']})
        for number in range(1, 1001):
            for attempt in range(5):
                response = http.get('https://data.alpaca.markets/v2/stocks/bars', params=params, timeout=60)
                if response.status_code != 429 and response.status_code < 500:
                    break
                time.sleep(min(2**attempt, 16))
            response.raise_for_status()
            path = a.output/f'page_{number:04d}.json'
            path.write_bytes(response.content)
            metadata['pages'].append(dict(file=path.name, sha256=sha256(path),
                retrieved_at_utc=datetime.now(timezone.utc).isoformat()))
            payload = response.json()
            for ticker, bars in (payload.get('bars') or {}).items():
                for bar in bars:
                    rows.append(dict(ticker=ticker,
                        session_date=pd.Timestamp(bar['t']).tz_convert('America/New_York').strftime('%Y-%m-%d'),
                        raw_close=bar['c'], raw_volume=bar['v']))
            save_json(a.output/'metadata.json', metadata)
            print('Raw reference page', number, flush=True)
            token = payload.get('next_page_token')
            if not token:
                break
            if token in seen:
                raise ValueError('Repeated page token; incomplete download preserved')
            seen.add(token); params['page_token'] = token
        else:
            raise ValueError('Page safety limit exceeded')
    frame = pd.DataFrame(rows)
    if frame.empty or frame.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Empty or duplicate raw observations')
    frame.to_csv(a.output/'raw_prices.csv', index=False)
    metadata.update(status='downloaded', rows=len(frame), csv_sha256=sha256(a.output/'raw_prices.csv'),
                    finished_at_utc=datetime.now(timezone.utc).isoformat())
    save_json(a.output/'metadata.json', metadata)


if __name__ == '__main__':
    main()
