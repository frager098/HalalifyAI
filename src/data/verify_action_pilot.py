"""Check one known AAPL dividend and split against preserved action evidence.

Pilot only: does not certify every company's action history or fill unknown actions.
"""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv
from .collect_price_bases import URL, parse_bars
from .reconciliation import run_id, save_json, sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--prices',type=Path,required=True)
    p.add_argument('--actions',type=Path,required=True)
    args=p.parse_args();load_dotenv(args.repo/'.env')
    key,secret=os.getenv('ALPACA_API_KEY'),os.getenv('ALPACA_SECRET_KEY')
    if not key or not secret: p.error('Local credentials required.')
    events={}
    for path in sorted(args.actions.glob('page_*.json')):
        for kind,records in json.loads(path.read_text()).get('corporate_actions',{}).items():
            for event in records:
                if event.get('symbol')=='AAPL' and ((kind=='cash_dividends' and event.get('ex_date')=='2016-02-04') or
                        (kind=='forward_splits' and event.get('ex_date')=='2020-08-31')):
                    events[kind]=event
    if set(events)!={'cash_dividends','forward_splits'}: raise ValueError('Pilot action evidence missing.')
    prices=pd.read_csv(args.prices);prices=prices[prices.ticker=='AAPL'].set_index('session_date')
    version='action_pilot_'+run_id();raw_folder=args.repo/'data/raw/action_pilots'/version
    raw_folder.mkdir(parents=True,exist_ok=False)
    checks=[];requests_meta=[]
    with requests.Session() as http:
        http.headers.update({'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
        for kind,event in events.items():
            date=pd.Timestamp(event['ex_date'])
            params=dict(symbols='AAPL',timeframe='1Day',feed='sip',adjustment='raw',asof='2025-12-31',limit=10000,
                start=(date-timedelta(days=10)).strftime('%Y-%m-%d')+'T00:00:00-05:00',
                end=(date+timedelta(days=10)).strftime('%Y-%m-%d')+'T23:59:59-05:00')
            response=http.get(URL,params=params,timeout=60);response.raise_for_status()
            path=raw_folder/(kind+'.json');path.write_bytes(response.content)
            payload=response.json()
            if payload.get('next_page_token'): raise ValueError('Unexpected truncated pilot response.')
            raw=pd.DataFrame(parse_bars(payload)).set_index('session_date').sort_index()
            ex=event['ex_date'];previous=raw.index[raw.index<ex][-1]
            before,after=prices.loc[previous],prices.loc[ex]
            raw_before,raw_after=raw.loc[previous],raw.loc[ex]
            if kind=='cash_dividends':
                observed=(before.adjusted_close/before.close)/(after.adjusted_close/after.close)
                expected=1-event['rate']/raw_before.close
                passed=abs(observed-expected)<0.001
                values=dict(observed_adjustment_ratio=float(observed),expected_ratio=float(expected),
                            tolerance=0.001)
            else:
                expected=event['new_rate']/event['old_rate']
                observed=(raw_before.close/before.close)/(raw_after.close/after.close)
                before_share=before.volume/raw_before.volume
                after_share=after.volume/raw_after.volume
                volume_ratio=before_share/after_share
                passed=abs(observed-expected)<0.01 and abs(volume_ratio-expected)<0.01
                values=dict(expected_split_ratio=expected,observed_price_factor=float(observed),
                            observed_volume_factor=float(volume_ratio),tolerance=0.01)
            checks.append(dict(kind=kind,ticker='AAPL',ex_date=ex,passed=bool(passed),**values))
            requests_meta.append(dict(parameters=params,raw_sha256=sha256(path)))
    report=dict(scope='AAPL dividend/split pilot only; no global readiness approval',checks=checks,
                source_price_sha256=sha256(args.prices),requests=requests_meta,
                full_action_coverage_verified=False)
    save_json(args.repo/'reports/validation'/version/'action_pilot.json',report)
    print(json.dumps(report['checks'],indent=2))
    if not all(c['passed'] for c in checks): raise SystemExit('Pilot failed; investigate before feature generation.')


if __name__=='__main__': main()
