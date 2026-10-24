"""Source-preserving disclosure extraction, not financial mapping or religious classification."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from copy import deepcopy
from lxml import etree
import pandas as pd


REVENUE_TOTAL_TAGS={'Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax',
    'RevenueFromContractWithCustomerIncludingAssessedTax','SalesRevenueGoodsNet','SalesRevenueServicesNet',
    'Revenue','RevenueFromContractsWithCustomers'}


def concept_kind(tag):
    local=tag.rsplit(':',1)[-1];lower=local.lower()
    if local in REVENUE_TOTAL_TAGS:return 'revenue_candidate'
    if local=='RevenuesNetOfInterestExpense':return 'net_revenue_candidate'
    if local in {'OtherNonoperatingIncomeExpense','OtherIncomeExpenseNet','NonoperatingIncomeExpense'}:
        return 'other_income_expense_unallocated_candidate'
    # 'Minority interest' means ownership, not earned interest. Searching for
    # the two words anywhere would wrongly classify many profit/tax concepts.
    if any(word in lower for word in ['minorityinterest','noncontrollinginterest','ownershipinterest']):return None
    if re.search(r'interest(?:anddividend|andfee|andfees|andother)?income|investmentincomeinterest|income(?:from)?interest',lower):
        if 'incometax' in lower:return 'tax_related_interest_candidate'
        if 'net' in lower or 'expense' in lower:return 'net_interest_or_income_expense_candidate'
        if 'dividend' in lower:return 'combined_interest_dividend_candidate'
        if 'fee' in lower:return 'combined_interest_fee_candidate'
        if 'other' in lower or ('investmentincome' in lower and lower!='investmentincomeinterest'):
            return 'combined_interest_other_income_candidate'
        return 'gross_interest_income_candidate'
    if 'interestreceived' in lower:return 'interest_cash_receipt_candidate'
    if 'investmentincome' in lower:return 'investment_income_unallocated_candidate'
    if ('revenue' in lower or 'sales' in lower) and not any(word in lower for word in
        ['deferred','unearned','cost','expense','tax','rate','remainingperformance','contractliabilit','percent','growth']):
        return 'other_revenue_related_candidate'
    return None


def interest_row_kind(label):
    lower=label.lower()
    if not re.search(r'\binterest\s+(?:and\s+(?:dividend|fee)s?\s+)?income\b',lower):return None
    if re.search(r'\bnet\b|expense',lower):return 'net_interest_or_income_expense_candidate'
    if 'dividend' in lower:return 'combined_interest_dividend_candidate'
    if 'fee' in lower:return 'combined_interest_fee_candidate'
    if 'other' in lower or 'investment' in lower:return 'combined_interest_other_income_candidate'
    return 'gross_interest_income_candidate'


def table_row_label(item):
    parent=item.getparent()
    while parent is not None and local_name(parent)!='tr':parent=parent.getparent()
    if parent is None:return None
    for cell in parent:
        if local_name(cell) not in {'td','th'}:continue
        if any(local_name(n)=='nonfraction' for n in cell.iter()):break
        text=re.sub(r'\s+',' ',' '.join(cell.itertext())).strip()
        if re.search('[A-Za-z]',text) and len(text)<180:return text
    return None


def numeric_value(text,scale='0',sign=None,format_name=''):
    """Support common SEC number transformations explicitly; unknown formats stay unknown."""
    fmt=format_name.rsplit(':',1)[-1].lower().replace('-','')
    allowed={'','numdotdecimal','numcommadecimal','numdash','zerodash','fixedzero'}
    if fmt not in allowed:return None,'unsupported_transform:'+format_name
    if fmt=='fixedzero':return '0','parsed' # Explicit XBRL Registry rule, not missing-value imputation.
    value=re.sub(r'[\s\u00a0$€£]','',text)
    if value in ['-','—','–']:
        if fmt in {'numdash','zerodash'}:value='0'
        else:return None,'dash_not_certified_zero'
    negative=value.startswith('(') and value.endswith(')')
    if negative:value=value[1:-1]
    value=value.replace('.','').replace(',','.') if fmt=='numcommadecimal' else value.replace(',','')
    try:
        number=Decimal(value)*(Decimal(10)**int(scale))
        if not number.is_finite():return None,'nonfinite_number'
        if negative or sign=='-':number=-abs(number)
        return str(number),'parsed'
    except (InvalidOperation,ValueError,OverflowError):return None,'unparsed_number'


def local_name(node):
    tag=node.tag if isinstance(node.tag,str) else ''
    return tag.rsplit('}',1)[-1].rsplit(':',1)[-1].lower()


def child_text(node,name):
    found=next((n for n in node.iter() if local_name(n)==name),None)
    return ''.join(found.itertext()).strip() if found is not None else None


def resources(soup):
    contexts={};units={}
    for context in (n for n in soup.iter() if local_name(n)=='context' and n.get('id')):
        dimensions=[]
        for member in (n for n in context.iter() if local_name(n) in {'explicitmember','typedmember'}):
            dimensions.append(dict(axis=member.get('dimension'),member=''.join(member.itertext()).strip(),
                                   member_type=local_name(member)))
        contexts[context.get('id')]=dict(entity_identifier=child_text(context,'identifier'),
            period_start=child_text(context,'startdate'),period_end=child_text(context,'enddate') or child_text(context,'instant'),
            dimensions=dimensions)
    for unit in (n for n in soup.iter() if local_name(n)=='unit' and n.get('id')):
        measures=[''.join(m.itertext()).strip() for m in unit.iter() if local_name(m)=='measure']
        units[unit.get('id')]='USD' if measures==['iso4217:USD'] else '/'.join(measures)
    return contexts,units


def business_section(text,ticker=None):
    """Ignore short table-of-contents matches; preserve the source body section."""
    boundary=r'(?m)^ *' if '\n' in text else r'\b'
    starts=list(re.finditer(boundary+r'items?\s*1(?:\s*(?:and|&)\s*2)?\s*[.\-:\u2013\u2014]?\s*business\b',text,re.I))
    # Some reports put a forward-looking statement note before the Business
    # title. Only consider a standalone Item 1 heading at a block boundary.
    starts.extend(re.finditer(r'(?m)^\s*item\s*1\s*[.\-:]?\s*(?=\n)',text,re.I))
    choices=[]
    for start in starts:
        end=re.search(boundary+r'item\s*(?:1\s*a\s*[.\-:\u2013\u2014]?\s*risk\s*factors|2\s*[.\-:\u2013\u2014]?\s*properties)\b',text[start.end():],re.I)
        if end:
            finish=start.end()+end.start();section=text[start.start():finish]
            if len(section)>=750:choices.append((len(section),section,start.start(),finish))
    rule='Longest formal Item 1 (or combined Items 1 and 2 Business) to Item 1A Risk Factors or Item 2 Properties; minimum 750 characters'
    if not choices:
        # These issuers use a reorganized 10-K. Literal section boundaries were
        # checked against their saved original reports; they are review excerpts,
        # not a claim that every incorporated Item 1 disclosure is included.
        headings={'INTC':r'Fundamentals? of Our Business','MCD':r'Business Summary',
                  'HON':r'About Honeywell','GE':r'About GE(?: Aerospace)?','MS':r'Business'}
        heading=headings.get(ticker)
        if heading:
            for start in re.finditer(r'(?im)^ *'+heading+r'(?= *[.\n])',text):
                end=re.search(r'(?im)^ *(?:Management[\u2019\x27]s Discussion(?: and Analysis)?|Risk Factors)\b',text[start.end():])
                if end:
                    finish=start.end()+end.start();section=text[start.start():finish]
                    if len(section)>=750:choices.append((len(section),section,start.start(),finish))
            rule='Issuer-specific reorganized 10-K business heading to next management discussion or risk heading; review excerpt, not certified complete Item 1'
    if not choices:return dict(status='section_not_reliably_identified',text=None)
    _,section,start,end=max(choices)
    return dict(status='extracted_requires_review',text=section,character_start=start,character_end=end,
                extraction_rule=rule)


def visible_report_text(root):
    """Keep block boundaries and words split across inline formatting tags."""
    blocks={'div','p','li','tr','td','th','table','h1','h2','h3','h4','h5','h6','br','section','header'}
    def walk(node):
        name=local_name(node)
        if name in {'script','style','head'} or (name=='header' and ':' in str(node.tag)):
            return ''
        parts=[node.text or '']
        for child in node:
            parts.extend([walk(child),child.tail or ''])
        joined=''.join(parts)
        return '\n'+joined+'\n' if name in blocks else joined
    text=walk(root)
    return re.sub(r'\n\s*\n','\n',re.sub(r'[^\S\n]+',' ',text)).strip()


def next_session(filing_date,calendar,acceptance_datetime=None):
    date=pd.Timestamp(filing_date).normalize()
    if acceptance_datetime:
        accepted=pd.Timestamp(acceptance_datetime)
        if accepted.tzinfo is not None:accepted=accepted.tz_convert('America/New_York').tz_localize(None)
        date=max(date,accepted.normalize())
    location=calendar.searchsorted(date,side='right')
    if location>=len(calendar):return None
    return calendar[location].strftime('%Y-%m-%d')


def parse_report(content,filing,calendar):
    # SEC primary reports are HTML/XHTML, including XML declarations. HTML mode
    # handles older imperfect markup; separate XBRL instances use XML mode below.
    soup=etree.fromstring(content,etree.HTMLParser(huge_tree=True,no_network=True))
    if soup is None:raise ValueError('Empty primary report')
    contexts,units=resources(soup);facts=[]
    available=next_session(filing['filing_date'],calendar,filing.get('acceptance_datetime'))
    issuer_names=[];issuer_ciks=[]
    for item in (n for n in soup.iter() if local_name(n)=='nonnumeric'):
        name=item.get('name','').rsplit(':',1)[-1]
        if name=='EntityRegistrantName':issuer_names.append(''.join(item.itertext()).strip())
        if name=='EntityCentralIndexKey':issuer_ciks.append(''.join(item.itertext()).strip())
    for ordinal,item in enumerate(n for n in soup.iter() if local_name(n)=='nonfraction'):
        concept=item.get('name','');kind=concept_kind(concept)
        if not kind and not re.search(r'income|revenue|interest',concept,re.I):continue
        label=table_row_label(item)
        row_kind=interest_row_kind(label or '')
        if row_kind:kind=row_kind
        if not kind:continue
        copied=deepcopy(item)
        for excluded in list(n for n in copied.iter() if local_name(n)=='exclude'):
            parent=excluded.getparent()
            if parent is not None:
                # Keep text after the excluded footnote, which may be part of the number.
                previous=excluded.getprevious()
                if excluded.tail:
                    if previous is not None:previous.tail=(previous.tail or '')+excluded.tail
                    else:parent.text=(parent.text or '')+excluded.tail
                parent.remove(excluded)
        displayed=''.join(copied.itertext()).strip()
        value,status=numeric_value(displayed,item.get('scale','0'),item.get('sign'),item.get('format',''))
        context_id=item.get('contextref');context=contexts.get(context_id,{})
        unit=units.get(item.get('unitref'))
        identifier=context.get('entity_identifier')
        identity_matches=bool(identifier and identifier.isdigit() and int(identifier)==int(filing['cik']))
        dims=context.get('dimensions',[])
        uid=hashlib.sha256(json.dumps([filing['sha256'],ordinal,concept,context_id,displayed]).encode()).hexdigest()
        facts.append(dict(fact_id=uid,ticker=filing['ticker'],cik=filing['cik'],
            accession_number=filing['accession_number'],form=filing['form'],filing_date=filing['filing_date'],
            available_from_session=available,source_url=filing['source_url'],source_sha256=filing['sha256'],
            source_kind='inline_xbrl',source_concept=concept,evidence_kind=kind,context_id=context_id,
            source_table_row_label=label,classification_basis='explicit_table_row_label' if row_kind else 'concept_name_candidate',
            period_start=context.get('period_start'),period_end=context.get('period_end'),dimensions=dims,
            unit=unit,value_decimal=value,displayed_value=displayed,scale=item.get('scale','0'),
            sign=item.get('sign'),format=item.get('format'),reported_decimals=item.get('decimals'),numeric_parse_status=status,
            issuer_context_matches=identity_matches,
            business_dimension_candidate=any(re.search(r'segment|product|service|business',d.get('axis') or '',re.I) for d in dims),
            review_status='candidate_not_approved'))
    text=visible_report_text(soup)
    business=(business_section(text,filing['ticker']) if filing['form'].startswith('10-K') else
              dict(status='quarterly_report_requires_business_update_review',text=None))
    record=dict(ticker=filing['ticker'],cik=filing['cik'],accession_number=filing['accession_number'],
        form=filing['form'],filing_date=filing['filing_date'],available_from_session=available,
        source_url=filing['source_url'],source_sha256=filing['sha256'],
        reported_issuer_names=sorted(set(issuer_names)),reported_issuer_ciks=sorted(set(issuer_ciks)),
        review_status='requires_human_review',**business)
    record['business_activity_text_candidates']=[]
    if business['text']:
        for match in list(re.finditer(r'\b(?:alcohol|alcoholic|beer|wine|spirits|pork|gambling|casino|tobacco|banking|insurance)\b',business['text'],re.I))[:60]:
            record['business_activity_text_candidates'].append(dict(term=match.group(),
                excerpt=business['text'][max(0,match.start()-180):match.end()+300],
                interpretation='literal_mention_only_not_a_business_exclusion'))
    snippets=[]
    matches=list(re.finditer(r'\binterest\s+(?:and\s+dividend\s+)?income\b|\bsegment\s+(?:revenues?|information)\b',text,re.I))
    for match in matches[:30]:
        snippets.append(dict(term=match.group(),character_start=max(0,match.start()-180),
            excerpt=text[max(0,match.start()-180):match.end()+500]))
    record['financial_text_candidates']=snippets
    record['financial_text_candidates_truncated']=len(matches)>30
    record['interest_table_rows']=[]
    for row in soup.iter():
        if local_name(row)!='tr':continue
        cells=[re.sub(r'\s+',' ',' '.join(cell.itertext())).strip() for cell in row if local_name(cell) in {'td','th'}]
        if cells and sum(map(len,cells))<=2500 and interest_row_kind(' '.join(cells[:2])):
            record['interest_table_rows'].append(dict(cells=cells,review_status='text_table_requires_period_and_unit_review'))
        if len(record['interest_table_rows'])>=50:break
    record['interest_table_row_limit_reached']=len(record['interest_table_rows'])>=50
    return record,facts


def parse_instance(content,filing,calendar):
    soup=etree.fromstring(content,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
    contexts,units=resources(soup);output=[]
    available=next_session(filing['filing_date'],calendar,filing.get('acceptance_datetime'))
    for ordinal,item in enumerate(n for n in soup.iter() if n.get('contextRef') and n.get('unitRef')):
        concept=(item.prefix+':' if item.prefix else '')+item.tag.rsplit('}',1)[-1]
        kind=concept_kind(concept)
        if not kind:continue
        context_id=item.get('contextRef');context=contexts.get(context_id,{})
        value,status=numeric_value(''.join(item.itertext()).strip())
        identifier=context.get('entity_identifier');dims=context.get('dimensions',[])
        output.append(dict(fact_id=hashlib.sha256(json.dumps([filing['instance_sha256'],ordinal,concept,context_id]).encode()).hexdigest(),
            ticker=filing['ticker'],cik=filing['cik'],accession_number=filing['accession_number'],form=filing['form'],
            filing_date=filing['filing_date'],available_from_session=available,source_url=filing['instance_url'],
            source_sha256=filing['instance_sha256'],source_kind='xbrl_instance',source_concept=concept,evidence_kind=kind,
            context_id=context_id,period_start=context.get('period_start'),period_end=context.get('period_end'),
            dimensions=dims,unit=units.get(item.get('unitRef')),value_decimal=value,
            displayed_value=''.join(item.itertext()).strip(),scale='0',sign=None,format=None,
            reported_decimals=item.get('decimals'),numeric_parse_status=status,
            issuer_context_matches=bool(identifier and identifier.isdigit() and int(identifier)==int(filing['cik'])),
            business_dimension_candidate=any(re.search(r'segment|product|service|business',d.get('axis') or '',re.I) for d in dims),
            review_status='candidate_not_approved'))
    return output


# Original-report note inventory shares the parser above. Screening imports are
# local to execution to avoid a parser -> rules -> parser import cycle.
import argparse
from pathlib import Path
from zipfile import ZipFile
import exchange_calendars as xc
from .reconciliation import sha256, save_json

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


def recover_notes(args):
    from ..screening.source_facts import read_facts
    from ..screening.run_yasaar import select_latest
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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    return recover_notes(args)


if __name__ == '__main__':
    main()
