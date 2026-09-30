"""Read-only Halalify input audit. Run with --repo PATH --out PATH.
Requires pandas/numpy; never edits inputs. Flags are not automatic deletions.
Calendar is explicitly scoped to 2016-2026 US equity full-day sessions.
"""
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, nearest_workday,
    sunday_to_monday, USMartinLutherKingJr, USPresidentsDay, GoodFriday,
    USMemorialDay, USLaborDay, USThanksgivingDay)

class EquityHolidays(AbstractHolidayCalendar):
    rules = [Holiday('New Year', month=1, day=1, observance=sunday_to_monday),
             USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
             Holiday('Juneteenth', month=6, day=19, start_date='2022-01-01', observance=nearest_workday),
             Holiday('Independence', month=7, day=4, observance=nearest_workday),
             USLaborDay, USThanksgivingDay,
             Holiday('Christmas', month=12, day=25, observance=nearest_workday)]

def sessions(start, end):
    holidays = EquityHolidays().holidays(start, end).union(pd.to_datetime(['2018-12-05', '2025-01-09']))
    return pd.bdate_range(start, end).difference(holidays)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit(repo, out):
    out.mkdir(parents=True, exist_ok=True)
    paths = [repo/'data/raw/alpaca_historical_prices.csv', repo/'data/raw/alpaca_data_summary.csv', repo/'data/processed/sec_historical_fundamentals_long.csv']
    rawpaths = sorted((repo/'data/raw/sec').glob('*_companyfacts.json'))
    manifest = {str(p): digest(p) for p in paths + rawpaths}
    checks=[]
    def check(name, count, severity='FAIL', note=''):
        checks.append(dict(check=name, status=severity if count else 'PASS', count=int(count), explanation=note))
    def save(name, frame):
        frame.to_csv(out/(name+'.csv'), index=False)
    a, summary, f = [pd.read_csv(p) for p in paths]
    a.insert(0,'source_row',np.arange(len(a))+2)
    f.insert(0,'source_row',np.arange(len(f))+2)
    required_a=['date','ticker','open','high','low','close','volume']
    required_f=['ticker','company_name','field','sec_concept','value','unit','period_start','period_end','filing_date','form','fiscal_year','fiscal_period','accession_number']
    if not set(required_a)<=set(a) or not set(required_f)<=set(f):
        raise ValueError('Input schema missing required columns')
    check('market_missing_cells',a[required_a].isna().sum().sum())
    check('market_duplicate_keys',a.duplicated(['ticker','date']).sum())
    a['date']=pd.to_datetime(a.date,errors='coerce')
    check('market_invalid_dates',a.date.isna().sum())
    for col in ['open','high','low','close','volume']:
        a[col]=pd.to_numeric(a[col],errors='coerce')
        check('market_nonfinite_'+col,(~np.isfinite(a[col])).sum())
        check('market_nonpositive_'+col,(a[col]<=0).sum())
    check('market_fractional_volume',(a.volume%1!=0).sum())
    check('market_invalid_ohlc',((a.high<a[['open','close','low']].max(axis=1))|(a.low>a[['open','close','high']].min(axis=1))).sum())
    check('market_unsorted_tickers',sum(not x.date.is_monotonic_increasing for _,x in a.groupby('ticker')))
    calendar=sessions('2016-01-01','2026-09-28')
    save('expected_sessions',pd.DataFrame({'date':calendar}))
    gaps=[]; coverage=[]
    for ticker,g in a.groupby('ticker'):
        start=pd.Timestamp('2018-10-31' if ticker=='LIN' else '2016-01-01')
        expected=calendar[calendar>=start]
        missing=expected.difference(g.date); unexpected=pd.DatetimeIndex(g.date).difference(expected)
        for kind,dates in [('missing',missing),('unexpected',unexpected)]:
            gaps.extend(dict(ticker=ticker,date=d,kind=kind) for d in dates)
        coverage.append(dict(ticker=ticker,rows=len(g),first_date=g.date.min(),last_date=g.date.max(),expected_rows=len(expected),missing_sessions=len(missing),unexpected_sessions=len(unexpected)))
    save('market_coverage',pd.DataFrame(coverage)); save('market_calendar_issues',pd.DataFrame(gaps,columns=['ticker','date','kind']))
    check('market_calendar_issues',len(gaps),note='LIN eligibility starts at its documented 2018-10-31 US listing; early-close days remain sessions.')
    actual=a.groupby('ticker').agg(rows=('date','size'),first_date=('date','min'),last_date=('date','max')).reset_index()
    for c in ['first_date','last_date']: summary[c]=pd.to_datetime(summary[c],errors='coerce')
    check('summary_mismatch',not actual.equals(summary[actual.columns].sort_values('ticker').reset_index(drop=True)))
    a=a.sort_values(['ticker','date']); a['daily_return']=a.groupby('ticker').close.pct_change(fill_method=None)
    jumps=a[a.daily_return.abs()>0.20].copy()
    save('price_moves_review',jumps)
    check('price_moves_over_20_percent',len(jumps),'REVIEW','Diagnostic threshold only; genuine market moves must not be deleted automatically.')
    check('sec_exact_duplicate_rows',f[required_f].duplicated().sum())
    check('sec_missing_required_cells',f[[c for c in required_f if c!='period_start']].isna().sum().sum())
    for c in ['period_start','period_end','filing_date']:
        old=f[c].copy(); f[c]=pd.to_datetime(f[c],errors='coerce')
        check('sec_invalid_'+c,(old.notna()&f[c].isna()).sum())
    f['value']=pd.to_numeric(f.value,errors='coerce')
    check('sec_nonfinite_value',(~np.isfinite(f.value)).sum())
    check('sec_negative_values',(f.value<0).sum(),'REVIEW')
    check('sec_period_after_filing',(f.period_end>f.filing_date).sum())
    check('sec_start_after_end',(f.period_start>f.period_end).sum())
    check('sec_revenue_missing_start',((f.field=='revenue')&f.period_start.isna()).sum())
    check('sec_unexpected_form',(~f.form.isin(['10-K','10-Q'])).sum())
    check('sec_invalid_accession',(~f.accession_number.astype(str).str.fullmatch(r'\d{10}-\d{2}-\d{6}')).sum())
    foreign=f[f.unit!='USD']; save('sec_non_usd',foreign)
    check('sec_non_usd',len(foreign),'REVIEW','Keep currencies separate; no automatic conversion or summing across units.')
    fields=['total_assets','cash','total_debt','revenue','accounts_receivable']
    missing=[]
    for t in sorted(a.ticker.unique()):
        for field in fields:
            if f[(f.ticker==t)&(f.field==field)&(f.unit=='USD')].empty: missing.append(dict(ticker=t,field=field))
    save('sec_missing_fields',pd.DataFrame(missing)); check('sec_missing_company_fields',len(missing),'REVIEW')
    key=['ticker','sec_concept','unit','period_start','period_end','filing_date','accession_number']
    conflicting=f.groupby(key,dropna=False).value.nunique().reset_index(name='distinct_values')
    conflicting=conflicting[conflicting.distinct_values>1]; save('sec_conflicting_same_filing',conflicting)
    check('sec_conflicting_same_filing',len(conflicting),'REVIEW')
    revised=f.groupby(['ticker','sec_concept','unit','period_start','period_end'],dropna=False).agg(versions=('filing_date','nunique'),distinct_values=('value','nunique')).reset_index()
    revised=revised[revised.distinct_values>1]; save('sec_changed_values_across_filings',revised)
    check('sec_changed_values_across_filings',len(revised),'REVIEW','May be restatements/context differences. Preserve as-filed versions; do not select latest globally.')
    revenue=f[f.field=='revenue'].copy(); revenue['duration_days']=(revenue.period_end-revenue.period_start).dt.days+1
    revenue['duration_group']=pd.cut(revenue.duration_days,[0,110,210,310,380,np.inf],labels=['about_quarter','about_half_year','about_nine_months','about_year','over_380_days'])
    save('revenue_duration_counts',revenue.groupby(['ticker','duration_group'],observed=True).size().reset_index(name='rows'))
    identities=[]; source_matches=set(); amendments=[]
    def token(t,concept,unit,o):
        def date(v): return '' if pd.isna(v) else str(v)[:10]
        return (t,concept,unit,date(o.get('start')),date(o.get('end')),date(o.get('filed')),str(o.get('accn')),float(o.get('val')))
    for p in rawpaths:
        d=json.loads(p.read_text(encoding='utf-8')); t=p.name.split('_companyfacts')[0]
        identities.append(dict(ticker=t,cik=d.get('cik'),entity_name=d.get('entityName'),raw_bytes=p.stat().st_size))
        for ns,concepts in d.get('facts',{}).items():
            for concept,item in concepts.items():
                for unit,observations in item.get('units',{}).items():
                    for o in observations:
                        if o.get('form') in ['10-K','10-Q','10-K/A','10-Q/A']:
                            if o.get('form','').endswith('/A'): amendments.append(dict(ticker=t,concept=concept,unit=unit,filing_date=o.get('filed'),accession=o.get('accn')))
                            if ns=='us-gaap': source_matches.add(token(t,concept,unit,o))
    mismatches=[]
    for r in f.to_dict('records'):
        o=dict(start=r['period_start'],end=r['period_end'],filed=r['filing_date'],accn=r['accession_number'],val=r['value'])
        if token(r['ticker'],r['sec_concept'],r['unit'],o) not in source_matches: mismatches.append(r)
    save('sec_source_mismatches',pd.DataFrame(mismatches,columns=f.columns)); check('sec_source_mismatches',len(mismatches))
    save('sec_entity_identity',pd.DataFrame(identities)); save('sec_raw_amendment_facts',pd.DataFrame(amendments))
    check('amended_facts_found_in_raw',len(amendments),'REVIEW','Amended facts require explicit relevance review.')
    result=dict(market_rows=len(a),sec_rows=len(f),raw_company_files=len(rawpaths),checks=checks,python=platform.python_version(),pandas=pd.__version__,numpy=np.__version__,input_sha256=manifest)
    (out/'validation_results.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    save('validation_checks',pd.DataFrame(checks))
    print(json.dumps({'market_rows':len(a),'sec_rows':len(f),'checks':checks},indent=2,default=str))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path,default=Path.cwd()); p.add_argument('--out',type=Path,default=Path('data/interim/validation')); args=p.parse_args(); audit(args.repo,args.out)
