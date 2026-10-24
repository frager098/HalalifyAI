"""Validate preserved inputs without editing them.
Run current snapshots: python -m src.data_pipeline.validate_source_data --phase2
The legacy flat-file audit remains available without --phase2.
Recovery writes a separate snapshot only when original hashes can be reproduced.
"""
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime, timezone
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

def restore_price_snapshot(source, metadata, destination):
    """Publish a new snapshot only after every page matches its original digest."""
    from src.data_pipeline.clean_source_data import recover_json_bytes
    recovered = []
    # Verify the complete set before writing any recovered source files.
    for item in metadata['pages']:
        content, method = recover_json_bytes(source/item['file'], item['sha256'])
        recovered.append((item, content, method))
    destination.mkdir(parents=True, exist_ok=False)
    for item, content, _ in recovered:
        (destination/item['file']).write_bytes(content)
    restored = dict(metadata, dataset_version=destination.name,
                    normalized_source_version=metadata['dataset_version'],
                    recovery=dict(original_directory=str(source), original_manifest_sha256=digest(source/'metadata.json'),
                                  method='Exact original digest after compact JSON serialization; no values changed',
                                  files=[dict(file=x['file'], method=m, original_disk_sha256=digest(source/x['file']))
                                         for x, _, m in recovered]))
    (destination/'metadata.json').write_text(json.dumps(restored, indent=2), encoding='utf-8')
    return restored


def phase2(repo, out):
    """Run the current snapshot review, reusing existing transformations and data."""
    from src.data_pipeline.audit_market_price_sources import audit as audit_prices, compare_raw_pages
    from src.data_pipeline.clean_source_data import (Config, run as clean, recover_json_bytes, calendar_sessions,
                                     coverage_report)
    from src.data_pipeline.build_point_in_time_fundamentals import run as fundamentals
    from src.data_pipeline.reconcile_market_price_history import price_events, identity_table, next_session_table
    repo = repo.resolve()
    out.mkdir(parents=True, exist_ok=False)
    price = repo/'data/raw/alpaca/alpaca_sip_20261009T110617242394Z'
    sec = repo/'data/raw/sec_snapshots/20261009T110657727507Z'
    interim = repo/'data/interim/prices'/price.name/'daily_prices.csv'
    model = repo/'data/processed/model_inputs/legacy_model_dataset_2026-10-09T115557Z/model_dataset.csv'
    load = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    pm, sm = load(price/'metadata.json'), load(sec/'metadata.json')
    checks = []
    def check(path, expected, group):
        actual = digest(path)
        method = 'original_bytes' if actual == expected else 'unresolved'
        if method == 'unresolved' and path.suffix == '.json':
            try:
                _, method = recover_json_bytes(path, expected)
            except (ValueError, TypeError):
                pass
        checks.append(dict(file=str(path.relative_to(repo)), group=group,
                           expected_sha256=expected, actual_sha256=actual,
                           disk_matches=actual == expected, recovery=method))
    for directory, items, group in [(price, pm['pages'], 'alpaca'), (sec, sm['files'], 'sec')]:
        for item in items:
            check(directory/item['file'], item['sha256'], group)
    check(sec/'company_tickers.json', sm['ticker_mapping_sha256'], 'mapping')
    check(interim, pm['normalized_sha256'], 'interim')
    check(model, load(model.with_name('targets_metadata.json'))['output_sha256'], 'model')
    checks = pd.DataFrame(checks)
    checks.to_csv(out/'source_checks.csv', index=False)
    print('Source hashes checked; comparing raw pages...', flush=True)
    price_audit, _, _ = audit_prices(model, price/'metadata.json', interim)
    prices = pd.read_csv(interim, low_memory=False)
    modeled = pd.read_csv(model, low_memory=False)
    page_summary, changed = compare_raw_pages(price, pm, prices)
    page_summary.to_csv(out/'raw_page_comparison.csv', index=False)
    changed.to_csv(out/'changed_market_values.csv', index=False)
    restored_dir = price.with_name(price.name+'_restored_json_v1')
    restorable = checks.loc[checks.group.eq('alpaca'), 'recovery'].ne('unresolved').all()
    cleaning = {'status': 'blocked_source_integrity'}
    if restorable:
        if not restored_dir.exists():
            restore_price_snapshot(price, pm, restored_dir)
        else:
            restored = load(restored_dir/'metadata.json')
            if (restored.get('recovery', {}).get('original_manifest_sha256') != digest(price/'metadata.json')
                    or restored['pages'] != pm['pages']
                    or restored.get('normalized_source_version') != price.name
                    or restored.get('normalized_sha256') != pm['normalized_sha256']):
                raise ValueError('Existing restored snapshot has different provenance')
        print('Cleaning recovered market snapshot...', flush=True)
        cleaning = clean(Config(root=str(repo), price_version=restored_dir.name, market_only=True))
    dates, calendar = calendar_sessions(pm['requested_start'], pm['requested_end'], prices, False)
    coverage, gaps = coverage_report(prices, dates, sorted(prices.ticker.unique()))
    gaps['disposition'] = 'unresolved'
    gaps.loc[gaps.ticker.eq('LIN') & gaps.session_date.lt('2018-10-31'), 'disposition'] = 'before_documented_listing'
    coverage['listing_start_evidence'] = coverage.ticker.map({'LIN': '2018-10-31'})
    coverage['unexplained_missing_sessions'] = coverage.ticker.map(
        gaps[gaps.disposition.eq('unresolved')].groupby('ticker').size()).fillna(0).astype(int)
    coverage.to_csv(out/'market_coverage.csv', index=False)
    gaps.to_csv(out/'calendar_issues.csv', index=False)
    events = price_events(modeled)
    events.to_csv(out/'price_event_dispositions.csv', index=False)
    identities = identity_table(modeled.ticker.unique(), sec)
    # Current identifiers from unverified sources must remain visibly unverified.
    identities['source_integrity_verified'] = identities.model_ticker.map({
        t: all(digest(sec/i['file']) == i['sha256'] for i in sm['files'] if i['ticker'] == t)
        for t in modeled.ticker.unique()})
    identities.to_csv(out/'identity_review.csv', index=False)
    timing = next_session_table(prices.loc[prices.ticker.eq('SPY'), 'session_date'])
    timing.to_csv(out/'decision_sessions.csv', index=False)
    print('Reviewing SEC candidate facts and unsupported concepts...', flush=True)
    evidence = {}
    sec_summary, _, _, sec_coverage, concepts, conflicts, panel = fundamentals(model, sec, restored_dir if restorable else price, evidence)
    sec_coverage.to_csv(out/'sec_coverage.csv', index=False)
    concepts.to_csv(out/'sec_concept_dispositions.csv', index=False)
    evidence['selected_facts'].to_csv(out/'sec_selected_facts.csv', index=False)
    conflicts.to_csv(out/'sec_fact_conflicts.csv', index=False)
    # Inspect excluded AAPL without using its unverified values as features.
    aapl_facts, aapl_sub = load(sec/'AAPL_companyfacts.json'), load(sec/'AAPL_submissions.json')
    aapl_observations = [o for c in ('Assets', 'CashAndCashEquivalentsAtCarryingValue')
                         for o in aapl_facts.get('facts', {}).get('us-gaap', {}).get(c, {}).get('units', {}).get('USD', [])]
    aapl_review = dict(disposition='excluded_from_SEC_features', trusted_companyfacts_copy_available=False,
        companyfacts_cik=aapl_facts.get('cik'), submissions_cik=aapl_sub.get('cik'),
        candidate_observations=len(aapl_observations),
        candidate_accessions=len({o.get('accn') for o in aapl_observations}),
        first_filed=min(o['filed'] for o in aapl_observations), last_filed=max(o['filed'] for o in aapl_observations),
        note='These are observations about unverified local files, not trusted financial inputs. Recoverable submissions alone does not certify Company Facts.')
    # Do not duplicate the full modeling table or the earlier exploratory panel.
    # These counts describe raw inputs; rolling warm-up and label availability are phase 3.
    research_ok = (cleaning.get('input_checksums_verified', False) and changed.empty
                   and page_summary.duplicate_keys.eq(0).all()
                   and coverage.unexplained_missing_sessions.eq(0).all()
                   and coverage.unexpected_sessions.eq(0).all()
                   and cleaning.get('price_rows_quarantined') == 0)
    inventory = dict(price_source=str(price.relative_to(repo)), sec_source=str(sec.relative_to(repo)),
        selected_price_source=str(restored_dir.relative_to(repo)) if restorable else None,
        manifest_sha256={str(p.relative_to(repo)): digest(p) for p in
                         [price/'metadata.json', sec/'metadata.json', model.with_name('targets_metadata.json')]
                         + ([restored_dir/'metadata.json'] if restorable else [])},
        interim=str(interim.relative_to(repo)), model=str(model.relative_to(repo)),
        price_request=pm.get('source_requests'), requested_start=pm['requested_start'], requested_end=pm['requested_end'],
        sec_retrieved_at=sm['retrieved_at'], sec_requests=[dict(file=i['file'], url=i.get('url'), cik=i.get('cik')) for i in sm['files']],
        observed_start=modeled.session_date.min(), observed_end=modeled.session_date.max(),
        older_iex=dict(path='data/raw/alpaca_historical_prices.csv', present=(repo/'data/raw/alpaca_historical_prices.csv').exists(),
                       selected=False, note='Legacy reviewed IEX facts are not SIP coverage facts'))
    report = dict(schema_version=1, generated_at=datetime.now(timezone.utc).isoformat(), inventory=inventory,
        environment=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__,
                         exchange_calendars=__import__('exchange_calendars').__version__),
        source_disk_mismatches=int((~checks.disk_matches).sum()),
        exact_digest_recoverable_files=int(checks.recovery.eq('compact_json_matches_original_digest').sum()),
        unrecovered_files=checks.loc[checks.recovery.eq('unresolved'), 'file'].tolist(),
        price_audit=price_audit, cleaning=cleaning, calendar=calendar,
        explained_prelisting_gaps=int(gaps.disposition.eq('before_documented_listing').sum()),
        unresolved_calendar_gaps=int(gaps.disposition.eq('unresolved').sum()),
        large_moves=int(events.large_return_review.sum()), adjustment_differences=int(events.return_difference_pp.abs().gt(1).sum()),
        issuer_event_contexts=int(events.documented_event.notna().sum()),
        independently_verified_price_events=int(events.price_independently_verified.sum()), sec=sec_summary,
        aapl_review=aapl_review,
        sec_candidate_observations=evidence['candidate_observations'],
        sec_changed_values_across_filings=evidence['changed_values_across_filings'],
        phase3=dict(market_research_input_ready=bool(research_ok), verified_without_limitations=False,
                    input_path=cleaning.get('output_dir', '')+'/prices_clean.csv' if research_ok else None,
                    company_rows=int(len(modeled)) if research_ok else 0, company_count=int(modeled.ticker.nunique()),
                    row_rule='All non-SPY rows in the named cleaned prices; preserve all quality flags. Phase 3 handles feature warm-up and future-label completeness.',
                    market_fields=['ticker','session_date','open','high','low','close','volume','adjusted_close'],
                    return_price_basis='provider all-adjusted close for stock and SPY returns, momentum and targets; split OHLC retained separately',
                    sec_features_ready=False, sec_features_allowed=[],
                    forbidden_as_predictors='Future targets, split assignments, provenance/review flags and future outcome dates',
                    signal_timing='After session t closes; earliest execution is next observed session. bar_available_at remains missing.',
                    close_to_close_target_is_executable_return=False),
        limitations=['Current 50-stock selection has survivorship/selection bias; not a compliant-stock universe.',
                     'All large moves retained with unresolved independent price verification; issuer news does not verify OHLC.',
                     'Corporate-action magnitudes and complete historical identity remain unverified.',
                     'SEC AAPL Company Facts cannot be recovered; original AAPL pair excluded from candidate panel.',
                     'SEC candidate panel is a filing-date reconstruction, not an archived as-filed vintage.',
                     'Debt/revenue/restricted cash/receivables remain unapproved; profit margin/market cap absent.'],
        code_sha256={str(p.relative_to(repo)): digest(p) for p in [repo/'src/data_pipeline'/n for n in
                     ['validate_source_data.py','clean_source_data.py','audit_market_price_sources.py',
                      'reconcile_market_price_history.py','build_point_in_time_fundamentals.py']]})
    report['steps'] = {
        '2.1':'Inventory and observed coverage recorded',
        '2.2':'All original expected/actual hashes recorded',
        '2.3':'All pages compared with retained interim columns; see changed_market_values.csv',
        '2.4':'AAPL reviewed and excluded from SEC features; Company Facts recovery unresolved',
        '2.5':'Exact original price bytes restored into a separate immutable version' if restorable else 'Blocked',
        '2.6':cleaning['status'], '2.7':'XNYS calendar checked; pre-LIN dates separately explained',
        '2.8':'Each large move retained with unresolved independent price verification',
        '2.9':'Every adjustment difference assigned an interpretation and review batch; verification stays false',
        '2.10':'All 50 issuer identifiers reviewed in five batches; full historical mappings remain open',
        '2.11':'After-close signal and next-session execution proxy recorded; missing delivery times preserved',
        '2.12':'Candidate facts retain source observation/accession; conflicts and revisions reviewed; SEC gate closed',
        '2.13':'Unsupported concept dispositions recorded issuer by issuer',
        '2.14':'Market-only research input allowed with stated limitations; no SEC predictors admitted'}
    if any(digest(repo/row.file) != row.actual_sha256 for row in checks.itertuples()):
        raise ValueError('An original input changed during validation')
    report['original_inputs_unchanged'] = True
    (out/'phase2_report.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    (out/'output_manifest.json').write_text(json.dumps({p.name: digest(p) for p in out.iterdir() if p.is_file()}, indent=2), encoding='utf-8')
    print(json.dumps(dict(report=str(out/'phase2_report.json'), phase3=report['phase3']), indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--out',type=Path)
    p.add_argument('--phase2',action='store_true',help='Validate current versioned snapshots and recover exact price bytes.')
    args=p.parse_args()
    if args.phase2:
        phase2(args.repo, args.out or args.repo/'reports/generated'/datetime.now(timezone.utc).strftime('phase2_%Y%m%dT%H%M%S%fZ'))
    else:
        audit(args.repo,args.out or args.repo/'data/interim/validation')
