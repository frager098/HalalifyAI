"""Prepare dated business text and numeric source candidates for screening review."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
from datetime import date
import hashlib
import json
import re
from pathlib import Path
import exchange_calendars as xcals
import pandas as pd
from .reconciliation import COMPANY_SYMBOLS,save_json,sha256
from .screening_disclosures import concept_kind,next_session,parse_report,parse_instance
from .evidence_archive import archive_runs,evidence_sha256


def companyfact_candidates(path,ticker,calendar,start='2015-01-01',end='2025-12-31'):
    data=json.loads(path.read_text(encoding='utf-8-sig'));source_hash=evidence_sha256(path)
    for taxonomy,concepts in data.get('facts',{}).items():
        for concept,definition in concepts.items():
            kind=concept_kind(concept)
            if not kind:continue
            for unit,observations in definition.get('units',{}).items():
                for fact in observations:
                    if fact.get('form') not in ['10-K','10-K/A','10-Q','10-Q/A']:continue
                    if not start<=fact.get('filed','')<=end:continue
                    value=str(fact['val']) if fact.get('val') is not None else None
                    yield dict(fact_id=hashlib.sha256(json.dumps([ticker,taxonomy,concept,unit,fact],sort_keys=True).encode()).hexdigest(),
                        ticker=ticker,cik=str(data['cik']).zfill(10),source_company_name=data.get('entityName'),
                        source_concept=taxonomy+':'+concept,source_label=definition.get('label'),
                        source_description=definition.get('description'),evidence_kind=kind,value_decimal=value,unit=unit,
                        period_start=fact.get('start'),period_end=fact.get('end'),filing_date=fact.get('filed'),
                        fiscal_year=fact.get('fy'),fiscal_period=fact.get('fp'),source_frame=fact.get('frame'),
                        available_from_session=next_session(fact['filed'],calendar),form=fact['form'],
                        accession_number=fact.get('accn'),source_kind='companyfacts',source_sha256=source_hash,
                        source_url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(data["cik"]):010d}.json',
                        filing_index_url=f'https://www.sec.gov/Archives/edgar/data/{int(data["cik"])}/{fact.get("accn", "").replace("-", "")}/{fact.get("accn", "")}-index.html',
                        dimensions=[],business_dimension_candidate=False,
                        numeric_parse_status='parsed' if value is not None else 'missing',
                        issuer_context_matches=None,review_status='candidate_not_approved')


def usable_candidate(row,as_of):
    """A usable source number still does NOT establish an approved screening metric."""
    try:
        value=Decimal(row['value_decimal'])
        start=date.fromisoformat(row['period_start']);end=date.fromisoformat(row['period_end'])
        return (value.is_finite() and row.get('unit')=='USD' and row.get('numeric_parse_status')=='parsed'
            and row.get('available_from_session') is not None and row['available_from_session']<=as_of
            and start<=end and row['period_end']<=row['filing_date']
            and row.get('issuer_context_matches') is True)
    except (TypeError,ValueError,ArithmeticError):return False


def original_fact_key(row):
    if row.get('dimensions') or row.get('issuer_context_matches') is False:return None
    try:
        number=Decimal(row['value_decimal'])
        if not number.is_finite():return None
        return (row['ticker'],str(int(row['cik'])),row['accession_number'],row['source_concept'],
                row.get('period_start'),row.get('period_end'),row.get('unit'),number)
    except (TypeError,ValueError,ArithmeticError):return None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',nargs='+',type=Path,default=[])
    p.add_argument('--archive',type=Path,default=None)
    p.add_argument('--repo',type=Path,default=Path.cwd());p.add_argument('--as-of',default='2025-12-31')
    p.add_argument('--output-version',default='sec_2015_2025_v2')
    a=p.parse_args();calendar=xcals.get_calendar('XNYS',start='2015-01-01',end='2026-12-31').sessions
    if not a.input and not a.archive:p.error('Supply saved folders or --archive')
    inputs=list(a.input);archive=None
    if a.archive:
        archive,runs=archive_runs(a.archive);inputs.extend(runs)
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.output_version):p.error('Use a simple version folder name')
    target=a.repo/'data/interim/screening_evidence'/a.output_version;target.mkdir(parents=True,exist_ok=True)
    summaries={t:dict(ticker=t,annual_reports_downloaded=0,quarterly_reports_downloaded=0,
        business_sections_extracted=0,numeric_candidates=0,usable_usd_candidates=0,
        usable_candidates_by_kind=Counter(),business_revenue_dimension_candidates=0,
        latest_business_filing=None,approved_prohibited_income=None,approved_interest_income=None,
        screening_status='needs_review',portfolio_eligible=False) for t in COMPANY_SYMBOLS}
    seen=set();seen_reports=set();seen_companyfacts=set();errors=[];parse_status=Counter();sources=[]
    original_keys={};companyfacts_pending=[];verification=Counter()
    def record(row,output):
        if row['fact_id'] in seen:return
        seen.add(row['fact_id']);s=summaries[row['ticker']];s['numeric_candidates']+=1
        if usable_candidate(row,a.as_of):
            s['usable_usd_candidates']+=1;s['usable_candidates_by_kind'][row['evidence_kind']]+=1
            if row.get('business_dimension_candidate') and 'revenue' in row['evidence_kind']:
                s['business_revenue_dimension_candidates']+=1
        parse_status[row.get('numeric_parse_status','unknown')]+=1
        output.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    with (target/'numeric_candidates.jsonl').open('w',encoding='utf-8') as numbers,(target/'business_evidence.jsonl').open('w',encoding='utf-8') as businesses:
        for folder in inputs:
            metadata=json.loads((folder/'metadata.json').read_text())
            sources.append(dict(folder=folder.as_posix(),metadata_sha256=evidence_sha256(folder/'metadata.json'),scope=metadata['scope']))
            for ticker,company in metadata['companies'].items():
                path=folder/company['companyfacts_file'];key=(ticker,evidence_sha256(path))
                if key[1]!=company['companyfacts_sha256']:raise ValueError('CompanyFacts snapshot changed')
                if key in seen_companyfacts:continue
                seen_companyfacts.add(key)
                for row in companyfact_candidates(path,ticker,calendar,metadata['scope']['start'],metadata['scope']['end']):
                    row['source_issuer_role']=metadata['scope'].get('issuer_role','study_issuer')
                    companyfacts_pending.append(row)
            catalog=json.loads((folder/'filing_catalog.json').read_text())
            for i,entry in enumerate(catalog):
                if entry['status']!='downloaded':
                    errors.append(dict(ticker=entry['ticker'],accession_number=entry['accession_number'],error=entry.get('error','Not downloaded')));continue
                key=(entry['cik'],entry['accession_number'])
                if key in seen_reports:continue
                seen_reports.add(key);ticker=entry['ticker'];s=summaries[ticker]
                if entry['form'].startswith('10-K'):s['annual_reports_downloaded']+=1
                else:s['quarterly_reports_downloaded']+=1
                try:
                    path=folder/entry['file']
                    if evidence_sha256(path)!=entry['sha256']:raise ValueError('Primary report checksum mismatch')
                    business,rows=parse_report(path.read_bytes(),entry,calendar)
                    business['source_file']=path.as_posix()
                    business['source_issuer_role']=metadata['scope'].get('issuer_role','study_issuer')
                    if entry.get('instance_file'):
                        instance=folder/entry['instance_file']
                        if evidence_sha256(instance)!=entry['instance_sha256']:raise ValueError('Instance checksum mismatch')
                        rows.extend(parse_instance(instance.read_bytes(),entry,calendar))
                    for row in rows:
                        row['source_issuer_role']=metadata['scope'].get('issuer_role','study_issuer')
                        key=original_fact_key(row)
                        if key and not row['dimensions'] and row['issuer_context_matches']:
                            original_keys[key]=row['available_from_session']
                        record(row,numbers)
                    if business['text'] and business['available_from_session'] and business['available_from_session']<=a.as_of:
                        s['business_sections_extracted']+=1
                        if not s['latest_business_filing'] or business['filing_date']>s['latest_business_filing']['filing_date']:
                            s['latest_business_filing']={k:business[k] for k in ['filing_date','accession_number','source_url','available_from_session']}
                    businesses.write(json.dumps(business,ensure_ascii=False,allow_nan=False)+'\n')
                except Exception as error:errors.append(dict(ticker=ticker,accession_number=entry['accession_number'],error=str(error)))
                if (i+1)%100==0:print('Extracted',i+1,'/',len(catalog),'reports from',folder.as_posix(),flush=True)
        for row in companyfacts_pending:
            key=original_fact_key(row)
            matched=key in original_keys if key else False
            status='matched_original_issuer_nondimensional_fact' if matched else 'not_verified_against_original_fact'
            row['original_filing_verification']=status;row['issuer_context_matches']=True if matched else None
            if matched:
                row['available_from_session']=max(row['available_from_session'],original_keys[key])
            if row['fact_id'] not in seen:verification[status]+=1
            record(row,numbers)
    for ticker,s in summaries.items():
        s['usable_candidates_by_kind']=dict(s['usable_candidates_by_kind'])
        s['remaining_review']=['Standard/edition not selected','Business and segment interpretation not approved',
            'Amounts are candidates; do not sum overlapping totals/components/periods',
            'Prohibited-income completeness not established; unknown is not zero',
            'CompanyFacts source names are unverified labels; issuer filing context controls identity']
        if not s['business_sections_extracted']:s['remaining_review'].append('Business section needs manual source extraction')
        if not s['usable_candidates_by_kind'].get('gross_interest_income_candidate',0):
            s['remaining_review'].append('Separate gross interest-income disclosure not established')
    report=a.repo/'reports/validation/screening_evidence'/a.output_version
    save_json(report/'coverage.json',dict(as_of_date=a.as_of,standard_selected=False,
        companies=list(summaries.values()),sources=sources,extraction_errors=errors,numeric_parse_status=dict(parse_status),
        total_numeric_candidates=len(seen),reports_processed=len(seen_reports),
        companyfacts_original_verification=dict(verification),
        numerical_mapping_approved=False,historical_daily_screening_certified=False,
        calendar='XNYS',calendar_version=xcals.__version__,
        raw_archive_sha256=sha256(a.archive) if a.archive else None,
        output_hashes={p.name:sha256(p) for p in target.glob('*.jsonl')}))
    save_json(target/'screening_review_packets.json',dict(as_of_date=a.as_of,
        status='evidence_collected_requires_review',companies=list(summaries.values()),
        business_evidence_file='business_evidence.jsonl',numeric_evidence_file='numeric_candidates.jsonl'))
    print('Evidence extraction finished:',len(seen),'numeric candidates;',len(seen_reports),'reports;',len(errors),'errors',flush=True)
    if archive:archive.close()
    if errors:raise SystemExit('Extraction incomplete; inspect coverage.json before using the handoff')


if __name__=='__main__':main()
