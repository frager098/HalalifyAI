"""Audit a dual-basis CSV against the fixed study calendar; do not alter source."""
import argparse
from pathlib import Path
import pandas as pd
from .collect_price_bases import validate
from .reconciliation import COMPANY_SYMBOLS, save_json, sha256
from .validate_data import sessions


def audit(path, out):
    frame=pd.read_csv(path)
    validate(frame)
    required=['adjusted_close','dataset_version','instrument_id','security_type','currency','adjustment_verified']
    if not set(required)<=set(frame): raise ValueError('Dual-basis schema is incomplete.')
    if not (frame.adjusted_close.gt(0) & frame.adjusted_close.lt(float('inf'))).all():
        raise ValueError('Invalid adjusted close.')
    calendar=sessions('2016-01-01','2025-12-31')
    expected_symbols=set(COMPANY_SYMBOLS+['SPY'])
    coverage=[]
    for ticker,g in frame.groupby('ticker'):
        dates=pd.DatetimeIndex(pd.to_datetime(g.session_date,errors='raise'))
        expected=calendar[calendar>=pd.Timestamp('2018-10-31')] if ticker=='LIN' else calendar
        available=expected.intersection(dates)
        coverage.append(dict(ticker=ticker,rows=len(g),missing_sessions=len(expected.difference(dates)),
            unexpected_sessions=len(dates.difference(expected)),
            first_date=dates.min().strftime('%Y-%m-%d'),last_date=dates.max().strftime('%Y-%m-%d'),
            first_possible_feature_date=available[60].strftime('%Y-%m-%d') if len(available)>60 else None))
    out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(coverage).to_csv(out/'reconciled_price_coverage.csv',index=False)
    results=dict(rows=len(frame),company_count=len(set(frame.ticker)-{'SPY'}),benchmark_symbols=['SPY'],
        source_sha256=sha256(path),missing_symbols=sorted(expected_symbols-set(frame.ticker)),
        unexpected_symbols=sorted(set(frame.ticker)-expected_symbols),
        missing_sessions=sum(x['missing_sessions'] for x in coverage),
        unexpected_sessions=sum(x['unexpected_sessions'] for x in coverage),
        currency_ok=bool(frame.currency.eq('USD').all()),
        first_possible_feature_date=calendar[60].strftime('%Y-%m-%d'),
        action_adjustment_verified=bool(frame.adjustment_verified.eq(True).all()),
        core_ready=False,
        remaining=['Independent corporate-action checks and issuer identities',
            'Exact 16 feature calculations and complete-window checks',
            'Future labels and chronological partition purges'],
        date_note='Potential feature date only; missing windows and unknown actions can delay readiness.')
    save_json(out/'reconciled_prices.json',results)
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices',type=Path,required=True)
    p.add_argument('--out',type=Path,default=Path('reports/validation/reconciliation'))
    args=p.parse_args();result=audit(args.prices,args.out)
    print(f"Checked {result['rows']} rows; missing sessions: {result['missing_sessions']}.")
    print('Feature/label and action readiness are separate from these structural checks.')


if __name__=='__main__': main()
