"""Run source-backed FTSE Yasaar research filters over all 50 study companies."""
import argparse,csv,hashlib,json
from collections import Counter
from datetime import date,datetime,timezone
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile
import importlib.metadata
import sys
from zoneinfo import ZoneInfo
import exchange_calendars as xc
from src.data.reconciliation import COMPANY_SYMBOLS,sha256,save_json
from src.data.screening_disclosures import next_session
from .source_facts import read_facts,mapped_research_facts
from .yasaar import balance_checks,overall
from .presentation import write_html
from .field_recovery import recovered_balance,recover_income_check,recover_reviewed_debt

def select_latest(catalog,asof,calendar):
    result={};amends=[]
    for prefix,r in catalog:
        available=next_session(r['filing_date'],calendar,r.get('acceptance_datetime'))
        if r.get('status')!='downloaded' or not available or available>asof or not r.get('report_date') or r['report_date']>asof:continue
        if r['form'].endswith('/A'):amends.append((prefix,r));continue
        key=(r['report_date'],r['filing_date'],r['accession_number'])
        old=result.get(r['ticker'])
        if not old or key>(old[1]['report_date'],old[1]['filing_date'],old[1]['accession_number']):result[r['ticker']]=(prefix,r)
    return result,amends

def business_review(evidence,assessments=None):
    # Explicit source-specific assessments after reading full segment introductions,
    # not a keyword classifier. Narrative is not assigned a fabricated percentage.
    t=evidence['ticker']; text=evidence.get('text','');status='needs_review';reason='Business revenue exposure and prohibited-income completeness require review'
    marker=None
    review=(assessments or {}).get(t)
    if (review and str(evidence.get('cik','')).lstrip('0')==str(review['cik']).lstrip('0')
            and evidence.get('accession_number')==review['accession_number']
            and evidence.get('source_sha256')==review['source_sha256']):
        marker=review['marker']
        if marker.lower() in text.lower():
            status=review['status'];reason=review['reason']
    # Streaming entertainment interpretation remains reviewable, not an automatic exclusion.
    if t=='NFLX':reason='Streaming films/TV is primary business; mapping to Yasaar entertainment category needs domain review'
    quote=None
    if marker:
        ix=text.lower().find(marker.lower());quote=' '.join(text[max(0,ix-60):ix+400].split()[:24])
    return dict(status=status,reason=reason,source_url=evidence.get('source_url'),
        accession_number=evidence.get('accession_number'),filing_date=evidence.get('filing_date'),
        available_from_session=evidence.get('available_from_session'),source_sha256=evidence.get('source_sha256'),
        assessment='research_assessment_not_domain_approved',excerpt=quote,
        prohibited_revenue_percentage=None)

def income_checks(path,annual,asof):
    grouped={t:[] for t in COMPANY_SYMBOLS}
    tags={'RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','SalesRevenueNet','Revenues','InterestIncomeNonOperating','InvestmentIncomeInterest'}
    for line in path.open(encoding='utf8'):
        r=json.loads(line); t=r.get('ticker')
        if t not in annual or r.get('source_kind') not in ['inline_xbrl','xbrl_instance']:continue
        a=annual[t][1]
        if r.get('accession_number')!=a['accession_number'] or r.get('dimensions') or r.get('unit')!='USD' or r.get('issuer_context_matches') is not True:continue
        tag=r.get('source_concept','').split(':')[-1]
        if tag not in tags or r.get('numeric_parse_status')!='parsed' or not r.get('available_from_session') or r['available_from_session']>asof:continue
        if not r.get('period_start') or r.get('period_end')!=a['report_date']:continue
        days=(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days
        if 330<=days<=380:grouped[t].append(r)
    out={}
    for t,rows in grouped.items():
        rev=None;interest=None
        for tag in ['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','SalesRevenueNet','Revenues']:
            rr=[r for r in rows if r['source_concept'].split(':')[-1]==tag]
            vals={(r['period_start'],r['period_end'],r['value_decimal']) for r in rr}
            if len(vals)==1:
                rev=rr[0];break
        for tag in ['InterestIncomeNonOperating','InvestmentIncomeInterest']:
            rr=[r for r in rows if r['source_concept'].split(':')[-1]==tag]
            vals={(r['period_start'],r['period_end'],r['value_decimal']) for r in rr}
            if len(vals)==1:interest=rr[0];break
        check=dict(status='needs_review',ratio=None,reason='Gross interest and/or complete prohibited-income amount not established')
        if rev and interest and rev['period_start']==interest['period_start'] and Decimal(rev['value_decimal'])>0 and Decimal(interest['value_decimal'])>=0:
            # A denominator of sales alone may understate required total revenue.
            # Therefore this is a candidate ratio, never a failure or pass decision.
            check.update(candidate_interest_to_reported_revenue=str(Decimal(interest['value_decimal'])/Decimal(rev['value_decimal'])),reason='Candidate annual ratio only: other income denominator and prohibited earnings are not fully mapped')
        check.update(revenue_candidate=rev,interest_candidate=interest)
        out[t]=check
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--notes',type=Path);p.add_argument('--api',type=Path)
    a=p.parse_args()
    config=json.loads((a.repo/'configs/yasaar_research.json').read_text());asof=config['as_of_date']
    recovery_manifest=None;api_manifest=None;recovery_mappings={}
    if config.get('field_recovery_enabled'):
        notes=a.notes or a.repo/'data/interim/screening/recovery_notes_20261020'
        api=a.api or a.repo/'data/raw/screening_recovery_20261020/companyfacts'
        mapping_path=a.repo/'configs/screening_recovery_mappings.json'
        recovery_hashes=dict(notes_manifest=sha256(notes/'manifest.json'),api_manifest=sha256(api/'metadata.json'),mappings=sha256(mapping_path))
        if recovery_hashes!=config['supplemental_source_hashes']:
            raise ValueError('Supplementary recovery sources differ from registered versions')
        recovery_manifest=json.loads((notes/'manifest.json').read_text())
        api_manifest=json.loads((api/'metadata.json').read_text())
        recovery_mappings=json.loads(mapping_path.read_text())
        if api_manifest.get('status')!='complete' or api_manifest.get('downloaded')!=50:
            raise ValueError('All 50 registered SEC API responses are required')
    assessments_path=a.repo/'configs/business_research_assessments.json'
    assessments=json.loads(assessments_path.read_text())['reviews']
    universe=json.loads((a.repo/'configs/screening_universe.json').read_text())['company_tickers']
    if len(universe)!=50 or len(set(universe))!=50 or set(universe)!=set(COMPANY_SYMBOLS):
        raise ValueError('Screening requires exactly the registered 50 companies; SPY is not a company candidate')
    expected_limits=dict(debt_assets_limit='0.33333',cash_items_assets_limit='0.33333',receivables_cash_assets_limit='0.50',noncompliant_income_limit='0.05',prohibited_business_revenue_limit='0.05')
    if any(Decimal(config[k])!=Decimal(v) for k,v in expected_limits.items()):
        raise ValueError('Configured thresholds differ from the registered FTSE Yasaar v4.6 initial filters')
    actual_hashes=dict(archive=sha256(a.archive),business=sha256(a.evidence/'business_evidence.jsonl'),numeric=sha256(a.evidence/'numeric_candidates.jsonl'))
    if actual_hashes!=config['expected_input_sha256']:raise ValueError('Evidence differs from the registered source version; re-audit before screening')
    calendar=xc.get_calendar('XNYS',start='2015-01-01',end='2026-12-31').sessions
    z=ZipFile(a.archive); manifest=json.loads(z.read('archive_manifest.json'));catalog=[]
    for prefix in ['annual_2015_2025_20261002','quarterly_2015_2025_20261002']:
        catalog.extend((prefix,r) for r in json.loads(z.read(prefix+'/filing_catalog.json')))
    latest,amends=select_latest(catalog,asof,calendar)
    annual,_=select_latest([(p,r) for p,r in catalog if r['form']=='10-K'],asof,calendar)
    if set(latest)!=set(universe) or set(annual)!=set(universe):
        raise ValueError('An eligible original financial/annual report is missing for a registered company')
    business={}
    for line in (a.evidence/'business_evidence.jsonl').open(encoding='utf8'):
        r=json.loads(line)
        if r.get('source_issuer_role')!='study_issuer' or not r.get('text') or not r.get('available_from_session') or r['available_from_session']>asof:continue
        if r.get('ticker') not in annual:continue
        annual_report=annual[r['ticker']][1]
        if (r.get('accession_number')!=annual_report['accession_number']
                or r.get('source_sha256')!=annual_report['sha256']):continue
        old=business.get(r['ticker'])
        if not old or r['filing_date']>old['filing_date']:business[r['ticker']]=r
    income=income_checks(a.evidence/'numeric_candidates.jsonl',annual,asof)
    details=[];flat=[];recovery=[]
    for t in universe:
        prefix,r=latest[t];content=z.read(prefix+'/'+r['file'])
        if hashlib.sha256(content).hexdigest()!=r['sha256']:raise ValueError('Original report hash mismatch '+t)
        facts=read_facts(content,r['cik']);source_url=r['source_url'];source_hash=r['sha256']
        if not facts and r.get('instance_file'):
            content=z.read(prefix+'/'+r['instance_file']);source_url=r['instance_url'];source_hash=r['instance_sha256']
            if hashlib.sha256(content).hexdigest()!=source_hash:raise ValueError('Instance hash mismatch '+t)
            facts=read_facts(content,r['cik'],True)
        all_facts=read_facts(content,r['cik'],bool(r.get('instance_file') and source_url==r.get('instance_url')),include_custom=True)
        candidates=[f for f in all_facts if f['period_end']==r['report_date'] and not f['period_start'] and any(k in f['concept'].lower() for k in ['debt','borrow','notes','receivable','cash','securit','investment','leaseliability'])]
        recovery.append(dict(ticker=t,source_url=source_url,source_sha256=source_hash,reporting_date=r['report_date'],candidates=candidates,note='Reported candidates, not approved totals. Custom concepts, mixed leases, investment types and overlapping totals need source-specific mapping. Missing gross income is never zero.'))
        facts=mapped_research_facts(facts,all_facts,t,r['cik'],config.get('research_custom_mappings',[]))
        checks=balance_checks(facts,r['report_date'],config);checks['income']=income[t]
        if recovery_manifest:
            note_entry=recovery_manifest['companies'][t];note_path=notes/note_entry['file']
            if sha256(note_path)!=note_entry['sha256']:raise ValueError('Recovered original notes changed: '+t)
            if sha256(api/(t+'_companyfacts.json'))!=api_manifest['files'][t]['sha256']:
                raise ValueError('Retained supplementary API response changed: '+t)
            packet=json.loads(note_path.read_text());financial=packet['financial']
            if (financial['accession_number']!=r['accession_number'] or financial['source_sha256']!=r['sha256']
                    or financial['cik']!=r['cik']):
                raise ValueError('Recovered facts belong to a different financial filing: '+t)
            company_config=dict(config,recover_apple_classification_table=False)
            override=recovery_mappings.get('company_overrides',{}).get(t)
            if override:
                if any(override[key]!=financial[key] for key in ['cik','accession_number','source_sha256']):
                    raise ValueError('Source-specific classification review does not match filing: '+t)
                company_config.update(override)
            checks=recovered_balance(financial['facts'],r['report_date'],checks,company_config)
            checks=recover_reviewed_debt(checks,financial,recovery_mappings.get('manual_financial_disclosures',[]),content,company_config)
            if packet['annual']['accession_number']!=annual[t][1]['accession_number']:
                raise ValueError('Recovered annual income uses a different report: '+t)
            checks['income']=recover_income_check(checks['income'],packet['annual'],recovery_mappings['manual_annual_disclosures'])
        b=business_review(business.get(t,dict(ticker=t,text='')),assessments)
        amendments=[v['accession_number'] for _,v in amends if v['ticker']==t and v['report_date']>=r['report_date']]
        financial_age=(date.fromisoformat(asof)-date.fromisoformat(r['report_date'])).days
        business_age=((date.fromisoformat(asof)-date.fromisoformat(b['filing_date'])).days
                      if b.get('filing_date') else None)
        stale=(financial_age>config['financial_max_age_days'] or business_age is None
               or business_age>config['business_max_age_days'])
        status,failed=overall(checks,b,bool(amendments) or stale)
        missing=[name for name in ['debt','cash_and_interest_items','receivables_and_cash','income']
                 if checks[name]['status'] not in ['passes_filter','fails_initial_filter']]
        if b['status'] not in ['passes_filter','fails_initial_filter']:missing.append('business_revenue_exposure')
        eligible=status=='passes_research_filters' and config['domain_approved'] is True
        record=dict(ticker=t,as_of_date=asof,reporting_date=r['report_date'],filing_date=r['filing_date'],available_from_session=next_session(r['filing_date'],calendar,r.get('acceptance_datetime')),source_url=source_url,source_sha256=source_hash,accession_number=r['accession_number'],cik=r['cik'],research_status=status,failed_checks=failed,checks=checks,business=b,amendments_requiring_review=amendments,financial_age_days=financial_age,business_disclosure_age_days=business_age,stale_evidence=stale,missing_or_incomplete_checks=missing,portfolio_eligible=eligible,domain_approved=config['domain_approved'])
        details.append(record)
        flat.append(dict(ticker=t,reporting_date=r['report_date'],research_status=status,failed_checks='; '.join(failed),debt_minimum_percent=round(Decimal(checks['debt']['ratio'])*100,4) if checks['debt']['ratio'] else '',cash_items_minimum_percent=round(Decimal(checks['cash_and_interest_items']['ratio'])*100,4) if checks['cash_and_interest_items']['ratio'] else '',receivables_cash_minimum_percent=round(Decimal(checks['receivables_and_cash']['ratio'])*100,4) if checks['receivables_and_cash']['ratio'] else '',income_status=income[t]['status'],business_status=b['status'],source_url=source_url))
    target=a.repo/'reports/screening/ftse_yasaar_2025';target.mkdir(parents=True,exist_ok=True)
    hashes=dict(**actual_hashes,config=sha256(a.repo/'configs/yasaar_research.json'),business_assessments=sha256(assessments_path),universe=sha256(a.repo/'configs/screening_universe.json'))
    if recovery_manifest:hashes.update(recovery_hashes)
    counts={label:sum(r['research_status']==label for r in details) for label in ['passes_research_filters','fails_initial_filters','needs_review']}
    executed_on=datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
    summary=dict(profile=config,companies=len(details),counts=counts,portfolio_eligible=sum(r['portfolio_eligible'] for r in details),input_hashes=hashes,executed_on=executed_on,run_finished_at_utc=datetime.now(timezone.utc).isoformat(),evidence_as_of=asof,not_current_market_screen=True,python=sys.version,packages={name:importlib.metadata.version(name) for name in ['lxml','pandas','exchange_calendars']},limitation='Initial-entry research filters; not official membership, continuing-member monitoring or a religious approval. Minimum ratios below limits are not passes. Gross interest plus all non-compliant income remains incomplete in the retained evidence.')
    save_json(a.repo/'data/interim/screening/ftse_yasaar_2025/field_candidates.json',dict(companies=recovery))
    save_json(target/'results.json',dict(summary=summary,companies=details))
    with (target/'results.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    lines=['# FTSE Yasaar research screen','',f'Executed {executed_on} with evidence available as of {asof}. Fixed 2026 version, retrospective initial-entry filters.','',f"Complete research passes: {counts['passes_research_filters']}; fail a filter: {counts['fails_initial_filters']}; need review: {counts['needs_review']}.",'','Needs review means insufficient evidence, not a halal verdict or a failure.','All companies remain excluded from approved portfolios until evidence and domain review are complete.','', '| Ticker | Research result | Failing filters | Minimum debt % |','|---|---|---|---|']
    for row in flat:lines.append(f"| {row['ticker']} | {row['research_status']} | {row['failed_checks'] or 'Incomplete evidence'} | {row['debt_minimum_percent']} |")
    (target/'results.md').write_text('\n'.join(lines),encoding='utf8')
    write_html(target,details)
    coverage=[]
    for record in details:
        c=record['checks']
        coverage.append(dict(ticker=record['ticker'],assets_found=bool(c['assets']),debt_amount_found=bool(c['debt'].get('components')),cash_amount_found=bool(c['cash_and_interest_items'].get('components')),receivable_amount_found=any('Receivable' in x['concept'] for x in c['receivables_and_cash'].get('components',[])),annual_revenue_candidate_found=bool(c['income'].get('revenue_candidate')),gross_interest_candidate_found=bool(c['income'].get('interest_candidate')),complete_prohibited_income=False))
    save_json(target/'field_coverage.json',dict(companies=coverage,counts={k:sum(bool(r[k]) for r in coverage) for k in coverage[0] if k!='ticker'}))
    save_json(target/'remaining_review.json',dict(companies=[dict(ticker=r['ticker'],research_status=r['research_status'],missing_or_incomplete_checks=r['missing_or_incomplete_checks'],financial_source=r['source_url'],business_source=r['business'].get('source_url'),next_actions=['Reconcile all borrowing components and investment types against original notes.','Review prohibited business revenue by product/segment; keyword absence is not evidence of zero.','Establish gross interest plus all prohibited income with a consistent total-revenue denominator.'],amendments=r['amendments_requiring_review'],stale_evidence=r['stale_evidence']) for r in details]))
    z.close()
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
