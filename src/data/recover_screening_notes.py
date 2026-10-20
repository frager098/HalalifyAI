"""Inventory full original notes, including custom tags and dimensional facts.

This expands the search without turning candidates into approved totals.
Original fiscal periods, contexts, source hashes and availability are retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

import exchange_calendars as xc
from lxml import etree

from .reconciliation import sha256, save_json
from .screening_disclosures import local_name, visible_report_text, next_session
from ..screening.source_facts import read_facts
from ..screening.run_yasaar import select_latest


RELEVANT = re.compile(r'asset|liabilit|debt|borrow|notes|cash|receivable|securit|invest|lease|interest|revenue|sales', re.I)


def table_rows(content):
    root = etree.fromstring(content, etree.HTMLParser(huge_tree=True,no_network=True))
    output = []
    for ordinal, row in enumerate(n for n in root.iter() if local_name(n)=='tr'):
        cells = [' '.join(' '.join(c.itertext()).split()) for c in row
                 if local_name(c) in ['th','td']]
        text = ' | '.join(cells)
        if RELEVANT.search(' '.join(cells[:2])) and len(text)<3500 and re.search(r'\d',text):
            output.append(dict(row_ordinal=ordinal,cells=cells))
    text = visible_report_text(root)
    snippets = []
    for match in re.finditer(r'\b(?:interest(?: and dividends?)? income|finance leases?|total debt|total borrowings|noncompliant|non-compliant|alcohol|tobacco|pork)\b',text,re.I):
        snippets.append(dict(term=match.group(),character_start=match.start(),
                             text=text[max(0,match.start()-160):match.end()+500]))
    return output, snippets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    config=json.loads((args.repo/'configs/yasaar_research.json').read_text())
    if sha256(args.archive)!=config['expected_input_sha256']['archive']:
        raise ValueError('Original archive differs from registered evidence')
    if (args.out/'manifest.json').exists():
        raise ValueError('Use a new output folder; retain earlier inventories')
    args.out.mkdir(parents=True,exist_ok=True)
    calendar=xc.get_calendar('XNYS',start='2015-01-01',end='2026-12-31').sessions
    with ZipFile(args.archive) as archive:
        catalog=[]
        for prefix in ['annual_2015_2025_20261002','quarterly_2015_2025_20261002']:
            catalog.extend((prefix,r) for r in json.loads(archive.read(prefix+'/filing_catalog.json')))
        latest,_=select_latest(catalog,config['as_of_date'],calendar)
        annual,_=select_latest([(p,r) for p,r in catalog if r['form']=='10-K'],config['as_of_date'],calendar)
        manifest=dict(as_of_date=config['as_of_date'],archive_sha256=sha256(args.archive),companies={})
        for ticker in json.loads((args.repo/'configs/screening_universe.json').read_text())['company_tickers']:
            roles={}
            cache={}
            for role,(prefix,filing) in [('financial',latest[ticker]),('annual',annual[ticker])]:
                accession=filing['accession_number']
                if accession in cache:
                    roles[role]=cache[accession];continue
                content=archive.read(prefix+'/'+filing['file'])
                if hashlib.sha256(content).hexdigest()!=filing['sha256']:
                    raise ValueError('Original report hash mismatch: '+ticker)
                facts=read_facts(content,filing['cik'],include_custom=True,include_dimensions=True)
                numeric_source=filing['source_url'];numeric_hash=filing['sha256']
                if not facts and filing.get('instance_file'):
                    instance=archive.read(prefix+'/'+filing['instance_file'])
                    if hashlib.sha256(instance).hexdigest()!=filing['instance_sha256']:
                        raise ValueError('Original instance hash mismatch: '+ticker)
                    facts=read_facts(instance,filing['cik'],xml=True,include_custom=True,include_dimensions=True)
                    numeric_source=filing['instance_url'];numeric_hash=filing['instance_sha256']
                relevant=[f for f in facts if RELEVANT.search(f['concept'])]
                rows,snippets=table_rows(content)
                record=dict(ticker=ticker,cik=filing['cik'],accession_number=accession,
                    report_date=filing['report_date'],filing_date=filing['filing_date'],
                    available_from_session=next_session(filing['filing_date'],calendar,filing.get('acceptance_datetime')),
                    source_url=filing['source_url'],source_sha256=filing['sha256'],
                    numeric_source_url=numeric_source,numeric_source_sha256=numeric_hash,
                    facts=relevant,table_rows=rows,narrative_findings=snippets,
                    status='source_candidates_not_approved_complete_totals')
                roles[role]=record;cache[accession]=record
            path=args.out/(ticker+'.json');save_json(path,roles)
            manifest['companies'][ticker]=dict(file=path.name,sha256=sha256(path),
                financial_candidates=len(roles['financial']['facts']),annual_candidates=len(roles['annual']['facts']))
            save_json(args.out/'manifest.json',manifest)
            print(ticker,'notes inventoried',flush=True)


if __name__=='__main__':
    main()
