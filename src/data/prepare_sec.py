"""Extract evidence, quarantine invalid facts, retain versions; NOT screening snapshots.

Run: python -m src.data.prepare_sec --input data/raw/sec
Outputs: data/interim/sec/<run>/ and reports/validation/<run>/.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .reconciliation import run_id, save_json, sha256
from .validate_data import sessions

# Candidates only: debt components/alternative cash concepts are never summed here.
CONCEPTS = {
    'total_assets': ['Assets'],
    'debt_component': ['LongTermDebtAndFinanceLeaseObligationsCurrent',
        'LongTermDebtAndFinanceLeaseObligationsNoncurrent', 'LongTermDebtCurrent',
        'LongTermDebtNoncurrent', 'LongTermDebt', 'LongTermDebtAndCapitalLeaseObligations',
        'ShortTermBorrowings', 'ShortTermBorrowingsAndCurrentPortionOfLongTermDebt',
        'DebtCurrent', 'LongTermDebtAndCapitalLeaseObligationsCurrent',
        'LongTermDebtAndCapitalLeaseObligationsNoncurrent'],
    'cash_candidate': ['CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
    'revenue_candidate': ['RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet', 'Revenues', 'SalesRevenueGoodsNet', 'SalesRevenueServicesNet'],
    'receivables_candidate': ['AccountsReceivableNetCurrent', 'AccountsNotesAndOtherReceivablesNetCurrent'],
    'net_income_candidate': ['NetIncomeLoss', 'ProfitLoss'],
}


def extract(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    ticker = path.name.split('_companyfacts')[0]
    # The ticker alone is not enough to validate issuer identity.
    cik = str(data.get('cik', '')).zfill(10)
    source_hash = sha256(path)
    rows = []
    for field, concepts in CONCEPTS.items():
        for tag in concepts:
            for unit, observations in data.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).items():
                for item in observations:
                    form = item.get('form', '')
                    if form not in ['10-K', '10-Q', '10-K/A', '10-Q/A']:
                        continue
                    accn = item.get('accn')
                    # Hash complete observation, including frame/context and accession.
                    identity = json.dumps([ticker, cik, tag, unit, item], sort_keys=True)
                    rows.append(dict(fact_id=hashlib.sha256(identity.encode()).hexdigest(),
                        ticker=ticker, instrument_id='US_'+ticker, cik=cik,
                        company_name=data.get('entityName'), metric_name=field,
                        taxonomy='us-gaap', source_tag=tag, value=item.get('val'), unit=unit,
                        period_start=item.get('start'), period_end=item.get('end'),
                        filed_date=item.get('filed'), form_type=form, accession_number=accn,
                        fiscal_year=item.get('fy'), fiscal_period=item.get('fp'),
                        frame=item.get('frame'), is_amendment=form.endswith('/A'),
                        accepted_at=None, statement_scope='unverified',
                        source_url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(accn).replace("-", "")}/'
                            if cik.isdigit() and accn else None,
                        raw_file_uri=str(path), raw_sha256=source_hash,
                        mapping_version='candidate_evidence_v1', review_status='unreviewed'))
    return rows


def classify_facts(frame, calendar):
    frame = frame.copy()
    reasons = pd.Series('', index=frame.index)
    def flag(mask, name):
        nonlocal reasons
        reasons.loc[mask] += name+';'
    value = pd.to_numeric(frame.value, errors='coerce')
    end = pd.to_datetime(frame.period_end, errors='coerce')
    start = pd.to_datetime(frame.period_start, errors='coerce')
    filed = pd.to_datetime(frame.filed_date, errors='coerce')
    flag(~np.isfinite(value), 'invalid_value')
    flag(frame.unit != 'USD', 'non_usd')
    flag(end.isna() | filed.isna(), 'invalid_required_date')
    flag(end > filed, 'period_after_filing')
    flag(frame.period_start.notna() & start.isna(), 'invalid_period_start')
    flag(start > end, 'start_after_end')
    flow = frame.metric_name.isin(['revenue_candidate', 'net_income_candidate'])
    flag(flow & start.isna(), 'missing_flow_period_start')
    # Negative net income is economically valid; negative debt/cash/receivables isn't corrected by abs().
    flag((value < 0) & ~frame.metric_name.eq('net_income_candidate'), 'negative_amount_needs_review')
    flag(frame.metric_name.eq('total_assets') & (value <= 0), 'nonpositive_assets')
    flag(frame.accession_number.isna(), 'missing_accession')
    available = []
    for date in filed:
        index = calendar.searchsorted(date, side='right') if pd.notna(date) else len(calendar)
        available.append(calendar[index].strftime('%Y-%m-%d') if index < len(calendar) else None)
    frame['available_from_session'] = available
    flag(frame.available_from_session.isna(), 'availability_outside_calendar')
    # Same observation repeated byte-for-byte is safely deduplicated; versions are not collapsed.
    duplicate_count = int(frame.duplicated('fact_id').sum())
    frame['quarantine_reason'] = reasons.str.rstrip(';')
    frame = frame.drop_duplicates('fact_id')
    conflict_key = ['ticker', 'source_tag', 'unit', 'period_start', 'period_end', 'accession_number', 'frame']
    conflicting = frame.groupby(conflict_key, dropna=False).value.transform('nunique') > 1
    frame.loc[conflicting, 'quarantine_reason'] = frame.loc[conflicting, 'quarantine_reason'].map(
        lambda x: (x+';' if x else '')+'conflicting_same_filing')
    quarantine = frame[frame.quarantine_reason != ''].copy()
    quarantine['review_status'] = 'ambiguous'
    usable = frame[frame.quarantine_reason == ''].copy()
    return usable, quarantine, duplicate_count


def prepare(input_folder, repo, xom_history=None):
    paths = sorted(input_folder.glob('*_companyfacts.json'))
    if xom_history is not None:
        payload = json.loads(xom_history.read_text(encoding='utf-8-sig'))
        if int(payload.get('cik', 0)) != 34088:
            raise ValueError('Historical XOM evidence must be predecessor CIK 34088.')
        paths = [path for path in paths if path.name != 'XOM_companyfacts.json'] + [xom_history]
    if not paths:
        raise ValueError(f'No companyfacts JSON files in {input_folder}')
    rows, hashes = [], {}
    for path in paths:
        print(f'Reading {path.name}...', flush=True)
        rows.extend(extract(path))
        hashes[str(path)] = sha256(path)
    if not rows:
        raise ValueError('No candidate financial facts found.')
    frame = pd.DataFrame(rows)
    # Current source filing dates start in 2009. Add the Sandy exchange closures
    # when extending the existing holiday calendar back before its original scope.
    calendar = sessions('2009-01-01', '2026-12-31').difference(
        pd.to_datetime(['2012-10-29', '2012-10-30']))
    usable, quarantine, duplicates = classify_facts(frame, calendar)
    version = 'sec_evidence_' + run_id()
    interim = repo / 'data/interim/sec' / version
    report = repo / 'reports/validation' / version
    interim.mkdir(parents=True, exist_ok=False)
    report.mkdir(parents=True, exist_ok=False)
    usable.to_csv(interim / 'financial_facts.csv', index=False)
    quarantine.to_csv(interim / 'quarantined_facts.csv', index=False)
    coverage = usable.groupby(['ticker', 'metric_name']).size().unstack(fill_value=0)
    coverage.to_csv(report / 'candidate_coverage.csv')
    summary = dict(status='intermediate_evidence_not_training_or_screening_ready',
        historical_xom_source=str(xom_history) if xom_history else None,
        input_rows=len(frame), retained_candidate_rows=len(usable), quarantined_rows=len(quarantine),
        exact_duplicate_rows_removed=duplicates, raw_source_sha256=hashes,
        quarantine_reason_counts=quarantine.quarantine_reason.value_counts().to_dict(),
        calendar_version='explicit_US_equity_sessions_2009_2026_v1_with_Sandy_closures',
        unresolved=['Issuer identity/history review (especially XOM and BAC)',
            'Debt, cash and revenue mappings require issuer-level review',
            'Four non-overlapping quarters required before TTM ratios',
            'Business and prohibited-income evidence not extracted',
            'SEC acceptance timestamps and statement scope not independently verified'],
        screening_ready=False, fundamental_features_ready=False)
    save_json(report / 'sec_preparation.json', summary)
    print(f'Candidate facts: {len(usable)}; quarantined: {len(quarantine)}')
    print(f'Output: {interim}')
    print('These are checked evidence records, NOT final debt totals or compliance verdicts.')
    return interim, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=Path('data/raw/sec'))
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--xom-history', type=Path, help='Predecessor XOM_companyfacts.json for the 2016-2025 study only.')
    args = p.parse_args()
    prepare(args.input.resolve(), args.repo.resolve(), args.xom_history.resolve() if args.xom_history else None)


if __name__ == '__main__':
    main()
