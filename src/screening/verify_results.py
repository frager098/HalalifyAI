"""Verify the executed report's cohort, arithmetic, availability and safety flags."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from src.data.reconciliation import save_json, sha256
from .yasaar import overall
from .accounting_bounds import validate_upper_proof
from .business_revenue import validate_business_revenue
from .evidence_review import validate_reviewed_result


def validate_results(result, universe):
    rows, summary = result['companies'], result['summary']
    tickers = [r['ticker'] for r in rows]
    if len(tickers) != 50 or len(set(tickers)) != 50 or set(tickers) != set(universe):
        raise ValueError('Incomplete or duplicate screening universe')
    counts = Counter(r['research_status'] for r in rows)
    if any(counts[key] != count for key, count in summary['counts'].items()):
        raise ValueError('Summary counts do not match the company records')
    if sum(summary['counts'].values()) != 50 or summary['companies'] != 50:
        raise ValueError('Summary total is not the registered cohort')
    if 'financial_check_counts' in summary:
        for key,expected in summary['financial_check_counts'].items():
            if dict(Counter(r['checks'][key]['status'] for r in rows))!=expected:
                raise ValueError('Financial check counts differ from records')
    eligible = 0
    for record in rows:
        if (record['as_of_date'] != summary['evidence_as_of']
                or record['reporting_date'] > record['as_of_date']
                or record['available_from_session'] > record['as_of_date']):
            raise ValueError('Selected financial evidence exceeds cutoff')
        if record['business'].get('available_from_session', '9999') > record['as_of_date']:
            raise ValueError('Business evidence is missing or future-available')
        blocked = bool(record['amendments_requiring_review']) or record['stale_evidence']
        status, failures = overall(record['checks'], record['business'], blocked)
        if status != record['research_status'] or failures != record['failed_checks']:
            raise ValueError('Stored decision does not match the rule results')
        allowed = status == 'passes_research_filters' and record['domain_approved'] is True
        if record['portfolio_eligible'] is not allowed:
            raise ValueError('Unsafe portfolio eligibility flag')
        eligible += allowed
        assets = record['checks']['assets']
        for kind,check in [('income',record['checks']['income']),('business',record['business'])]:
            if check.get('reviewed_evidence'):
                validate_reviewed_result(check,kind,summary['profile'],record['as_of_date'])
        if record['business'].get('prohibited_revenue_minimum_ratio'):
            validate_business_revenue(record['business'], summary['profile']['prohibited_business_revenue_limit'])
        for key in ['debt', 'cash_and_interest_items', 'receivables_and_cash']:
            check = record['checks'][key]
            if check.get('upper_bound_proof'):
                limit_key={'debt':'debt_assets_limit','cash_and_interest_items':'cash_items_assets_limit','receivables_and_cash':'receivables_cash_assets_limit'}[key]
                validate_upper_proof(check,summary['profile'][limit_key],record['reporting_date'])
            if check['ratio'] is None:
                continue
            numerator = sum(Decimal(c['value']) for c in check['components'])
            if (Decimal(check['minimum_amount']) != numerator
                    or Decimal(check['ratio']) != numerator / Decimal(assets['value'])):
                raise ValueError('Financial ratio arithmetic mismatch')
        if len(record['source_sha256']) != 64:
            raise ValueError('Original source hash missing')
    if summary['portfolio_eligible'] != eligible:
        raise ValueError('Eligible-stock count mismatch')
    return dict(companies=50, counts=dict(counts), portfolio_eligible=eligible,
                universe_exact=True, no_duplicate_tickers=True,
                arithmetic_matches=True, decisions_recomputed=True,
                no_future_selected_sources=True, unsafe_eligibility_flags=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--report', type=Path, help='Explicit versioned results.json')
    args = parser.parse_args()
    report_path = args.report or args.repo/'reports/screening/ftse_yasaar_2025/results.json'
    result = json.loads(report_path.read_text())
    universe = json.loads((args.repo/'configs/screening_universe.json').read_text())['company_tickers']
    verified = validate_results(result, universe)
    verified['results_sha256'] = sha256(report_path)
    if args.compare:
        previous = {r['ticker']: r for r in json.loads(args.compare.read_text())['companies']}
        for record in result['companies']:
            old = previous[record['ticker']]
            if old['research_status'] != record['research_status']:
                raise ValueError('Reproduction changed a research decision')
            for key in ['debt', 'cash_and_interest_items', 'receivables_and_cash']:
                if old['checks'][key]['ratio'] != record['checks'][key]['ratio']:
                    raise ValueError('Reproduction changed a financial ratio')
                for field in ['status','maximum_ratio','upper_bound_proof']:
                    if old['checks'][key].get(field)!=record['checks'][key].get(field):
                        raise ValueError('Reproduction changed a financial proof or decision')
            if old['business']!=record['business']:
                raise ValueError('Reproduction changed the business evidence')
        verified['prior_retained_source_decisions_and_ratios_reproduced'] = True
    config=json.loads((args.repo/'configs/yasaar_research.json').read_text())
    save_json(args.repo/config.get('validation_output','reports/validation/screening_20261020')/'result_checks.json', verified)
    print(json.dumps(verified, indent=2))


if __name__ == '__main__':
    main()
