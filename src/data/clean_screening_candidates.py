"""Remove lexical false revenue matches; never infer approved financial amounts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from .extract_screening_reports import usable_candidate,original_fact_key
from .screening_disclosures import numeric_value
from .reconciliation import save_json,sha256


def retain_candidate(row):
    if row['evidence_kind']!='other_revenue_related_candidate':return True
    concept=row['source_concept'].rsplit(':',1)[-1]
    # Lowercasing AvailableForSaleSecurities creates the substring "sales".
    # Cash proceeds on asset/security sales also are not sales revenue.
    return ('revenue' in concept.lower() or bool(re.search(r'Sales(?=[A-Z]|$)|^sales(?=[A-Z]|$)',concept))) and 'proceeds' not in concept.lower()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--output-version',default='sec_2015_2025_v2');a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.output_version):p.error('Invalid version')
    folder=a.repo/'data/interim/screening_evidence'/a.output_version
    report=a.repo/'reports/validation/screening_evidence'/a.output_version/'coverage.json'
    coverage=json.loads(report.read_text());summaries={r['ticker']:r for r in coverage['companies']}
    for s in summaries.values():
        s.update(numeric_candidates=0,usable_usd_candidates=0,usable_candidates_by_kind=Counter(),business_revenue_dimension_candidates=0)
    source=folder/'numeric_candidates.jsonl';temporary=folder/'numeric_candidates.cleaned.tmp'
    removed=Counter();parsing=Counter();verification=Counter();total=0;original_keys={};fixed_zero_records=0
    with source.open(encoding='utf-8') as original,temporary.open('w',encoding='utf-8') as output:
        for line in original:
            row=json.loads(line)
            if not retain_candidate(row):removed[row['source_concept']]+=1;continue
            if row.get('source_kind') in {'inline_xbrl','xbrl_instance'}:
                if (row.get('format') or '').rsplit(':',1)[-1]=='fixed-zero':fixed_zero_records+=1
                if row.get('numeric_parse_status')=='unsupported_transform:ixt:fixed-zero':
                    row['value_decimal'],row['numeric_parse_status']=numeric_value(row['displayed_value'],row.get('scale','0'),row.get('sign'),row.get('format') or '')
                key=original_fact_key(row)
                if key and row.get('issuer_context_matches') is True:original_keys[key]=row['available_from_session']
            elif row.get('source_kind')=='companyfacts':
                key=original_fact_key(row);matched=key in original_keys if key else False
                row['original_filing_verification']='matched_original_issuer_nondimensional_fact' if matched else 'not_verified_against_original_fact'
                row['issuer_context_matches']=True if matched else None
                if matched:row['available_from_session']=max(row['available_from_session'],original_keys[key])
            output.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');total+=1;s=summaries[row['ticker']];s['numeric_candidates']+=1
            parsing[row.get('numeric_parse_status','unknown')]+=1
            if row.get('source_kind')=='companyfacts':verification[row['original_filing_verification']]+=1
            if usable_candidate(row,coverage['as_of_date']):
                s['usable_usd_candidates']+=1;s['usable_candidates_by_kind'][row['evidence_kind']]+=1
                if row.get('business_dimension_candidate') and 'revenue' in row['evidence_kind']:s['business_revenue_dimension_candidates']+=1
    temporary.replace(source)
    for s in summaries.values():s['usable_candidates_by_kind']=dict(s['usable_candidates_by_kind'])
    previous=coverage.get('lexical_revenue_cleanup',{}).get('removed_by_concept',{})
    removed.update(previous)
    coverage.update(total_numeric_candidates=total,numeric_parse_status=dict(parsing),
        explicit_fixed_zero_records=fixed_zero_records,
        companyfacts_original_verification=dict(verification),
        lexical_revenue_cleanup=dict(removed_records=sum(removed.values()),removed_by_concept=dict(removed),
            rule='Require Revenue or a distinct CamelCase Sales word; reject asset/security sale proceeds. No numerical totals are approved.'),
        output_hashes={f.name:sha256(f) for f in folder.glob('*.jsonl')})
    save_json(report,coverage)
    packets=json.loads((folder/'screening_review_packets.json').read_text());packets['companies']=list(summaries.values())
    save_json(folder/'screening_review_packets.json',packets)
    print('Retained',total,'numeric source candidates; removed',sum(removed.values()),'lexical revenue false matches')


if __name__=='__main__':main()
