"""Collect split-only and total-return-adjusted daily bars into NEW snapshots.

Run: python -m src.data.collect_price_bases
No old CSV is changed. Raw pages remain evidence; action checks remain required.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .reconciliation import COMPANY_SYMBOLS, run_id, save_json, sha256

URL = 'https://data.alpaca.markets/v2/stocks/bars'


def parse_bars(payload):
    rows = []
    for ticker, bars in (payload.get('bars') or {}).items():
        for bar in bars:
            date = pd.Timestamp(bar['t'])
            if date.tzinfo is None:
                raise ValueError('Provider timestamp must include its timezone.')
            rows.append(dict(ticker=ticker,
                             session_date=date.tz_convert('America/New_York').strftime('%Y-%m-%d'),
                             open=bar['o'], high=bar['h'], low=bar['l'],
                             close=bar['c'], volume=bar['v']))
    return rows


def validate(frame):
    if frame.empty:
        raise ValueError('No bars returned.')
    if frame.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Duplicate sessions returned; inspect preserved pages.')
    numeric = frame[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(numeric).all().all():
        raise ValueError('Nonfinite price/volume.')
    if (numeric[['open', 'high', 'low', 'close']] <= 0).any().any() or (numeric.volume < 0).any():
        raise ValueError('Invalid price/volume.')
    if ((numeric.high < numeric[['open', 'close', 'low']].max(axis=1)) |
            (numeric.low > numeric[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC values.')


def combine_bases(split, adjusted, version):
    validate(split)
    validate(adjusted)
    split_keys = set(zip(split.ticker, split.session_date))
    adjusted_keys = set(zip(adjusted.ticker, adjusted.session_date))
    if split_keys != adjusted_keys:
        raise ValueError('Price series have different session keys; do not silently drop rows.')
    merged = split.merge(adjusted[['ticker', 'session_date', 'close']],
                         on=['ticker', 'session_date'], suffixes=('', '_adjusted'), validate='one_to_one')
    merged = merged.rename(columns={'close_adjusted': 'adjusted_close'})
    merged['dataset_version'] = version
    # These IDs identify the study instrument, not a verified SEC issuer mapping.
    merged['instrument_id'] = 'US_' + merged.ticker
    merged['security_type'] = np.where(merged.ticker == 'SPY', 'etf_benchmark', 'common_stock')
    merged['currency'] = 'USD'
    merged['dividend_per_share'] = np.nan
    merged['split_ratio'] = np.nan
    merged['bar_available_at'] = None
    merged['adjustment_verified'] = False
    merged['data_quality_flags'] = 'action_evidence_not_verified'
    return merged.sort_values(['ticker', 'session_date']).reset_index(drop=True)


def collect(repo, symbols, start, end, http):
    version = 'alpaca_sip_' + run_id()
    folder = repo / 'data/raw/alpaca' / version
    folder.mkdir(parents=True, exist_ok=False)
    metadata = dict(dataset_version=version, provider='alpaca_sip', status='started',
                    retrieved_at=datetime.now(timezone.utc).isoformat(), pages=[],
                    requested_symbols=symbols, requested_start=start, requested_end=end,
                    adjustment_verified=False, ohlc_share_basis='split_adjusted',
                    volume_share_basis='split_adjusted',
                    adjusted_close_policy='Alpaca adjustment=all: split, dividend, spin-off',
                    core_ready=False,
                    packages={'pandas': pd.__version__, 'numpy': np.__version__, 'requests': requests.__version__})
    frames = {}
    try:
        for adjustment in ['split', 'all']:
            params = dict(symbols=','.join(symbols), timeframe='1Day',
                          start=pd.Timestamp(start, tz='America/New_York').isoformat(),
                          end=(pd.Timestamp(end, tz='America/New_York') + pd.Timedelta(hours=23,minutes=59,seconds=59)).isoformat(),
                          feed='sip', currency='USD', adjustment=adjustment,
                          limit=10000, sort='asc', asof=end)
            metadata.setdefault('source_requests', []).append(dict(endpoint=URL, parameters=params.copy()))
            rows, tokens = [], set()
            page = 0
            while True:
                page += 1
                print(f'{adjustment}: downloading page {page}...', flush=True)
                response = http.get(URL, params=params, timeout=(15, 60))
                if response.status_code != 200:
                    raise RuntimeError(f'Alpaca HTTP {response.status_code}; check access/credentials.')
                raw_path = folder / f'{adjustment}_{page:04d}.json'
                raw_path.write_bytes(response.content)
                metadata['pages'].append(dict(file=raw_path.name, sha256=sha256(raw_path),
                                             retrieved_at=datetime.now(timezone.utc).isoformat()))
                payload = response.json()
                rows.extend(parse_bars(payload))
                token = payload.get('next_page_token')
                if not token:
                    break
                if token in tokens:
                    raise ValueError('Repeated page token.')
                tokens.add(token)
                params['page_token'] = token
                time.sleep(0.25)
            frames[adjustment] = pd.DataFrame(rows)
            if set(frames[adjustment].ticker) != set(symbols):
                raise ValueError('One or more requested symbols are absent; inspect raw pages.')
        prices = combine_bases(frames['split'], frames['all'], version)
        if not prices.session_date.between(start, end).all():
            raise ValueError('Provider returned sessions outside requested bounds.')
        interim = repo / 'data/interim/prices' / version
        interim.mkdir(parents=True, exist_ok=False)
        prices.to_csv(interim / 'daily_prices.csv', index=False)
        summary = prices.groupby('ticker').agg(rows=('session_date', 'size'),
                                               first_date=('session_date', 'min'), last_date=('session_date', 'max')).reset_index()
        report = repo / 'reports/validation' / version
        report.mkdir(parents=True, exist_ok=False)
        summary.to_csv(report / 'price_coverage.csv', index=False)
        metadata.update(status='collected_requires_action_and_calendar_review',
                        normalized_csv=str(interim / 'daily_prices.csv'),
                        normalized_sha256=sha256(interim / 'daily_prices.csv'),
                        coverage_report_uri=str(report / 'price_coverage.csv'))
        print(summary.to_string(index=False))
        print(f'Saved: {interim / "daily_prices.csv"}')
        print('Collection finished; action evidence and complete session coverage still need review.')
        return interim / 'daily_prices.csv'
    except Exception as error:
        metadata.update(status='failed', error=str(error))
        raise
    finally:
        save_json(folder / 'metadata.json', metadata)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--symbols', nargs='+', default=COMPANY_SYMBOLS+['SPY'])
    p.add_argument('--start', default='2016-01-01')
    p.add_argument('--end', default='2025-12-31')
    args = p.parse_args()
    if args.start > args.end or len(set(args.symbols)) != len(args.symbols):
        p.error('Date range must be ordered; symbols must be unique.')
    for date in [args.start, args.end]:
        datetime.strptime(date, '%Y-%m-%d')
    load_dotenv(args.repo / '.env')
    key, secret = os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')
    if not key or not secret:
        p.error('Set Alpaca credentials in the local .env; never paste them into chat.')
    with requests.Session() as http:
        http.headers.update({'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret})
        http.mount('https://', HTTPAdapter(max_retries=Retry(total=4, backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'])))
        collect(args.repo.resolve(), args.symbols, args.start, args.end, http)


if __name__ == '__main__':
    main()
