"""Export the exact unresolved-company request and an auditable before/after."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from src.data.reconciliation import save_json,sha256


def build_gap_report(result, before):
    rows=result['companies']
    by_old={r['ticker']:r for r in before['companies']}
    new_clearances=Counter()
    for key in ['debt','cash_and_interest_items','receivables_and_cash','income']:
        new_clearances[key]=sum(r['checks'][key]['status']=='passes_filter' for r in rows)
        new_clearances[key]-=before['financial_check_counts'][key].get('passes_filter',0)
    requests=[]
    for r in rows:
        if r['research_status']!='needs_review':continue
        requests.append(dict(ticker=r['ticker'],cik=r['cik'],information_cutoff=r['as_of_date'],
            methodology='FTSE Yasaar public initial-entry filters v4.6; retrospective research',
            financial_period_end=r['reporting_date'],
            annual_source=r['business']['source_url'],financial_source=r['source_url'],
            missing_checks=';'.join(r['missing_or_incomplete_checks']),
            business_request='Reviewed prohibited product/activity revenue, amount, total-revenue denominator, period, source and completeness basis',
            income_request='Gross interest plus all non-compliant income, total-revenue denominator, period, source and completeness basis',
            historical_request='Only information available by cutoff; identify original filing and first availability; label later analyst interpretations separately',
            unknown_policy='Unknown/ambiguous remains unknown; never supply invented zero or simulated data'))
    changes=[dict(ticker=r['ticker'],before=by_old[r['ticker']]['research_status'],after=r['research_status'],
                  reason=r['business']['reason']) for r in rows
             if by_old[r['ticker']]['research_status']!=r['research_status']]
    return dict(before=before['summary_counts'],after=result['summary']['counts'],
        newly_cleared_financial_tests=dict(new_clearances),
        newly_cleared_financial_test_total=sum(new_clearances.values()),
        changed_stock_decisions=changes,unresolved_companies=len(requests),
        all_required_gaps_closed=not requests,missing_income_not_imputed=True,
        provider_data_received=False,provider_contact_sent=False,purchase_made=False),requests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    args=parser.parse_args()
    target=args.repo/'reports/screening/ftse_yasaar_2025'
    validation=args.repo/'reports/validation/screening_gap_resolution_20261020'
    results=target/'results.json'
    report,requests=build_gap_report(json.loads(results.read_text()),
        json.loads((validation/'before.json').read_text()))
    report['results_sha256']=sha256(results)
    contact_path=validation/'provider_access.json'
    if contact_path.exists():
        contact=json.loads(contact_path.read_text())
        report['provider_contact_attempted']=contact['contact_attempted']
        report['provider_contact_delivery_confirmed']=contact['delivery_confirmed']
        report['provider_contact_status']=contact['delivery_status']
        # Keep the legacy field limited to confirmed delivery, not button clicks.
        report['provider_contact_sent']=contact['delivery_confirmed']
    save_json(validation/'after.json',report)
    request_path=target/'data_request.csv'
    if requests:
        with request_path.open('w',newline='',encoding='utf8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(requests[0]))
            writer.writeheader();writer.writerows(requests)
    elif request_path.exists():
        # Preserve a zero-row request with explicit headers instead of stale companies.
        request_path.write_text('ticker,cik,information_cutoff,missing_checks\n',encoding='utf8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
