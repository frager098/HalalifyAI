"""Verify BAC candidate facts against original SEC filing identities and XBRL.

Preserves all inputs. Produces an identity-enriched BAC-only interim CSV and
separate unmatched records, not financial totals or Shariah verdicts.
Run from the repository root; see docs/bac_identity_resolution.md.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

FORMS = {'10-K', '10-Q', '10-K/A', '10-Q/A'}
CIK = '0000070858'
TAGS = {'Assets', 'LongTermDebtAndFinanceLeaseObligationsCurrent',
    'LongTermDebtAndFinanceLeaseObligationsNoncurrent', 'LongTermDebtCurrent',
    'LongTermDebtNoncurrent', 'LongTermDebt', 'LongTermDebtAndCapitalLeaseObligations',
    'ShortTermBorrowings', 'ShortTermBorrowingsAndCurrentPortionOfLongTermDebt',
    'DebtCurrent', 'LongTermDebtAndCapitalLeaseObligationsCurrent',
    'LongTermDebtAndCapitalLeaseObligationsNoncurrent',
    'CashAndCashEquivalentsAtCarryingValue',
    'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
    'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
    'Revenues', 'SalesRevenueGoodsNet', 'SalesRevenueServicesNet',
    'AccountsReceivableNetCurrent', 'AccountsNotesAndOtherReceivablesNetCurrent',
    'NetIncomeLoss', 'ProfitLoss'}


def local(tag):
    return tag.rsplit('}', 1)[-1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_instance(path):
    root = ET.parse(path).getroot()
    headers = {}
    for item in root:
        if '/dei/' in item.tag and local(item.tag) in {
                'EntityRegistrantName', 'EntityCentralIndexKey', 'DocumentType'}:
            headers.setdefault(local(item.tag), set()).add((item.text or '').strip())
    names = headers.get('EntityRegistrantName', set())
    ciks = {v.zfill(10) for v in headers.get('EntityCentralIndexKey', set())}
    forms = headers.get('DocumentType', set())
    identity = bool(names) and all(
        re.sub(r'[^a-z]', '', name.lower()) in {
            'bankofamericacorporation', 'bankofamericacorpde'}
        for name in names) and ciks == {CIK} and bool(forms) and forms <= FORMS
    contexts, units = {}, {}
    for item in root:
        if local(item.tag) == 'context':
            identifiers = [x.text for x in item.iter() if local(x.tag) == 'identifier']
            dimensioned = any(local(x.tag) in {'segment', 'scenario'} for x in item.iter())
            periods = {local(x.tag): x.text for x in item.iter()
                       if local(x.tag) in {'instant', 'startDate', 'endDate'}}
            if not dimensioned and identifiers and all(
                    str(v).zfill(10) == CIK for v in identifiers):
                contexts[item.attrib['id']] = (
                    periods.get('startDate'), periods.get('instant', periods.get('endDate')))
        if local(item.tag) == 'unit':
            measures = [x.text for x in item.iter() if local(x.tag) == 'measure']
            if len(measures) == 1 and measures[0].split(':')[-1] == 'USD':
                units[item.attrib['id']] = 'USD'
    facts = set()
    for item in root:
        tag = local(item.tag)
        context = contexts.get(item.attrib.get('contextRef'))
        unit = units.get(item.attrib.get('unitRef'))
        if tag not in TAGS or '/us-gaap/' not in item.tag or not context or not unit:
            continue
        try:
            value = Decimal(item.text or '')
        except InvalidOperation:
            continue
        if value.is_finite():
            facts.add((tag, context[0], context[1], unit, value))
    return identity, {k: sorted(v) for k, v in headers.items()}, facts


def find_instance_url(index_html, index_url):
    for row in re.findall(r'<tr\b[^>]*>.*?</tr>', index_html, re.I | re.S):
        description = re.sub(r'<[^>]+>', '', row)
        if not re.search(r'EX-101\.INS|EXTRACTED\s+XBRL INSTANCE DOCUMENT', description, re.I):
            continue
        for href in re.findall(r'href=["\']([^"\']+)["\']', row, re.I):
            url = urljoin(index_url, href)
            parsed = urlparse(url)
            if (parsed.hostname == 'www.sec.gov' and parsed.path.endswith('.xml')
                    and parsed.path.rsplit('/', 1)[0] == urlparse(index_url).path.rsplit('/', 1)[0]):
                return url
    raise ValueError('No extracted/standalone XBRL instance in filing index')


def fetch(url, path, user_agent):
    if path.exists():
        return
    import requests
    for attempt in range(4):
        response = requests.get(url, headers={'User-Agent': user_agent}, timeout=90)
        if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        path.write_bytes(response.content)
        time.sleep(.2)
        return


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify(companyfacts, submissions, financial_csv, repo, user_agent, run=None):
    cf = json.loads(companyfacts.read_text(encoding='utf-8-sig'))
    sub = json.loads(submissions.read_text(encoding='utf-8-sig'))
    if (str(cf.get('cik')).zfill(10) != CIK or
            str(sub.get('cik')).zfill(10) != CIK or 'BAC' not in sub.get('tickers', [])):
        raise ValueError('BAC inputs must identify CIK 70858 and submissions ticker BAC')
    with financial_csv.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        all_rows = list(reader)
        rows = [row for row in all_rows if row['ticker'] == 'BAC']
    if not rows or any(row['cik'].zfill(10) != CIK for row in rows):
        raise ValueError('Expected nonempty BAC candidate rows with CIK 70858')
    # No identity normalization is allowed for a value absent from this raw source.
    source_keys = {
        (tag, unit, x.get('start') or '', x.get('end') or '', x.get('accn'),
         x.get('form'), x.get('filed'), Decimal(str(x['val'])))
        for tag in TAGS
        for unit, observations in cf.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).items()
        for x in observations if x.get('form') in FORMS
    }
    run = run or 'bac_identity_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    raw = repo / 'data/raw/sec_identity' / run
    interim = repo / 'data/interim/sec_identity' / run
    reports = repo / 'reports/validation/bac_identity' / run
    for folder in [raw, interim, reports]:
        folder.mkdir(parents=True, exist_ok=True)
    filings = {}
    for number, accn in enumerate(sorted({row['accession_number'] for row in rows}), 1):
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accn):
            raise ValueError('Invalid accession number')
        folder = raw / accn
        folder.mkdir(exist_ok=True)
        url = f'https://www.sec.gov/Archives/edgar/data/70858/{accn.replace("-", "")}/{accn}-index.htm'
        record = {'accession_number': accn, 'index_url': url, 'verified': False}
        try:
            index = folder / 'index.htm'
            fetch(url, index, user_agent)
            instance_url = find_instance_url(index.read_text(encoding='utf-8'), url)
            instance = folder / 'instance.xml'
            fetch(instance_url, instance, user_agent)
            valid, headers, facts = parse_instance(instance)
            record.update(verified=valid, headers=headers, instance_url=instance_url,
                index_sha256=digest(index), instance_sha256=digest(instance), fact_keys=facts)
        except Exception as error:
            record['error'] = str(error)
        filings[accn] = record
        print(f'Filing {number}: {accn}: identity={record["verified"]}', flush=True)
    accepted, unmatched, replacements = [], [], {}
    extras = ['source_company_name', 'identity_review_status', 'identity_evidence_url',
              'filing_fact_match_status', 'identity_review_reason']
    for row in rows:
        out = dict(row)
        out['source_company_name'] = row['company_name']
        filing = filings[row['accession_number']]
        start = row['period_start'] or None
        key = (row['source_tag'], start, row['period_end'], row['unit'], Decimal(row['value']))
        source_key = (row['source_tag'], row['unit'], row['period_start'], row['period_end'],
                      row['accession_number'], row['form_type'], row['filed_date'], Decimal(row['value']))
        matched = filing['verified'] and key in filing.get('fact_keys', set()) and source_key in source_keys
        out.update(identity_review_status='verified' if matched else 'needs_review',
            identity_evidence_url=filing.get('instance_url', filing['index_url']),
            filing_fact_match_status='exact_consolidated_context_match' if matched else 'unverified',
            identity_review_reason='' if matched else 'Identity, raw-source or original filing fact match not established')
        if matched:
            out['company_name'] = 'Bank of America Corporation'
            # Overall review_status remains unreviewed: mapping/economic meaning is separate.
            out['statement_scope'] = 'non_dimensional_issuer_context_verified'
        (accepted if matched else unmatched).append(out)
        replacements[tuple(row[field] for field in fields)] = out
    write_csv(interim / 'BAC_identity_verified_financial_facts.csv', accepted, fields + extras)
    write_csv(interim / 'BAC_identity_needs_review.csv', unmatched, fields + extras)
    combined = [replacements.get(tuple(row[field] for field in fields), row) for row in all_rows]
    write_csv(interim / 'financial_facts_identity_updated.csv', combined, fields + extras)
    public = [{k: v for k, v in value.items() if k != 'fact_keys'} for value in filings.values()]
    summary = dict(status='resolved_for_verified_records' if not unmatched else 'partially_resolved',
        cik=CIK, ticker='BAC', normalized_company_name='Bank of America Corporation',
        companyfacts_source_name=cf.get('entityName'), submissions_source_name=sub.get('name'),
        candidate_rows=len(rows), verified_rows=len(accepted), needs_review_rows=len(unmatched),
        full_dataset_rows=len(all_rows), other_company_rows_changed=0,
        filing_count=len(filings), identity_verified_filings=sum(x['verified'] for x in filings.values()),
        raw_sources={str(p): digest(p) for p in [companyfacts, submissions, financial_csv]},
        filings=public, screening_ready=False,
        limits=['Identity/individual reported fact verification is not reviewed debt/TTM mapping',
                'No Shariah eligibility decision; historical filing availability remains unchanged',
                'Original CompanyFacts and financial CSV remain unchanged'])
    (reports / 'bac_identity_resolution.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (raw / 'metadata.json').write_text(json.dumps(dict(retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256=summary['raw_sources'], filings=public), indent=2), encoding='utf-8')
    print(f'Verified rows: {len(accepted)}; needs review: {len(unmatched)}; report: {reports}', flush=True)
    return summary, interim, reports


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--companyfacts', type=Path, required=True)
    p.add_argument('--submissions', type=Path, required=True)
    p.add_argument('--financial-csv', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--user-agent', required=True, help='Project name and real SEC contact')
    p.add_argument('--run', help='Explicit run ID, permits resuming cached preserved downloads')
    args = p.parse_args()
    if args.run and not re.fullmatch(r'[A-Za-z0-9_-]+', args.run):
        p.error('Run ID must be a simple folder name')
    verify(args.companyfacts.resolve(), args.submissions.resolve(), args.financial_csv.resolve(),
           args.repo.resolve(), args.user_agent, args.run)


if __name__ == '__main__':
    main()
