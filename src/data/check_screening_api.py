"""Cross-check current CompanyFacts against fixed original filing contexts.

Only exact accession/period/value matches on eligible historical filings are
counted. A current API response never replaces historical original evidence.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from .reconciliation import sha256,save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api',type=Path,required=True)
    parser.add_argument('--notes',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    api_manifest=json.loads((args.api/'metadata.json').read_text())
    note_manifest=json.loads((args.notes/'manifest.json').read_text())
    if api_manifest.get('status')!='complete' or api_manifest.get('downloaded')!=50:
        raise ValueError('SEC API collection is not complete')
    cutoff=note_manifest['as_of_date'];companies=[]
    for ticker,entry in note_manifest['companies'].items():
        api_entry=api_manifest['files'][ticker];api_path=args.api/f'{ticker}_companyfacts.json'
        note_path=args.notes/entry['file']
        if sha256(api_path)!=api_entry['sha256'] or sha256(note_path)!=entry['sha256']:
            raise ValueError('Supplementary evidence hash changed')
        api=json.loads(api_path.read_text());notes=json.loads(note_path.read_text())
        if int(api['cik'])!=int(notes['financial']['cik']):raise ValueError('Issuer mismatch')
        index=set();future=0;historical=0
        for concept,data in api.get('facts',{}).get('us-gaap',{}).items():
            for row in data.get('units',{}).get('USD',[]):
                if row.get('filed','9999')>cutoff or row.get('end','9999')>cutoff:
                    future+=1;continue
                historical+=1
                index.add((concept,row.get('start'),row.get('end'),Decimal(str(row['val'])),row.get('accn')))
        per_role={}
        for role,source in notes.items():
            found=set();missed=set()
            for fact in source['facts']:
                if fact.get('dimensions') or 'us-gaap' not in fact['namespace']:continue
                if fact['period_end']!=source['report_date']:continue
                key=(fact['concept'],fact['period_start'],fact['period_end'],Decimal(fact['value']),source['accession_number'])
                (found if key in index else missed).add(key)
            per_role[role]=dict(exact_original_fact_matches=len(found),not_in_current_api=len(missed),
                accession_number=source['accession_number'],original_source=source['source_url'])
        companies.append(dict(ticker=ticker,api_sha256=api_entry['sha256'],api_url=api_entry['url'],
            api_observations_after_cutoff_excluded=future,eligible_historical_api_observations=historical,
            roles=per_role,decision_source='original eligible filings, never latest API values'))
    save_json(args.out,dict(cutoff=cutoff,companies=companies,api_files=50,
        api_manifest_sha256=sha256(args.api/'metadata.json'),notes_manifest_sha256=sha256(args.notes/'manifest.json'),
        current_api_used_as_historical_truth=False,
        exact_original_fact_matches=sum(r['roles'][role]['exact_original_fact_matches'] for r in companies for role in r['roles'])))
    print('All 50 SEC API snapshots checked against original filing contexts.')


if __name__=='__main__':main()
