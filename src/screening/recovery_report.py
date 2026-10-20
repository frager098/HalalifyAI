"""Report actual recovered fields and unresolved disclosure needs for all 50."""
import argparse
import json
from pathlib import Path

from src.data.reconciliation import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    args=parser.parse_args();repo=args.repo
    report=repo/'reports/validation/screening_field_recovery_20261020'
    results=json.loads((repo/'reports/screening/ftse_yasaar_2025/results.json').read_text())
    before=json.loads((report/'before.json').read_text())
    old={r['ticker']:r for r in before['companies']}
    coverage=json.loads((repo/'reports/screening/ftse_yasaar_2025/field_coverage.json').read_text())
    api=json.loads((report/'api_crosscheck.json').read_text())
    rows=[]
    for r in results['companies']:
        recovered=r['checks']['income'].get('recovered_interest_disclosures',[])
        rows.append(dict(ticker=r['ticker'],previous_status=old[r['ticker']]['research_status'],
            current_status=r['research_status'],changed=old[r['ticker']]['research_status']!=r['research_status'],
            financial_source=r['source_url'],annual_source=r['business'].get('source_url'),
            rounded_receivable_reconciled=any(c.get('rounding_reconciled') for c in r['checks']['receivables_and_cash'].get('components',[])),
            separate_gross_interest_candidate=bool(r['checks']['income'].get('interest_candidate')),
            combined_or_net_interest_only=bool(recovered) and not bool(r['checks']['income'].get('interest_candidate')),
            original_interest_disclosures_examined=len(recovered),
            unresolved_checks=r['missing_or_incomplete_checks'],
            unresolved_income_reason='Complete prohibited-activity revenue and income are not established; neither missing nor combined/net income is zero.',
            decision_basis='Only original historical filings determine ratios; current API observations do not replace them.'))
    summary=dict(before=before['counts'],after=results['summary']['counts'],api_files_downloaded=api['api_files'],
        original_facts_crossmatched_to_api=api['exact_original_fact_matches'],
        field_coverage=coverage['counts'],changed_companies=[r['ticker'] for r in rows if r['changed']],
        all_required_fields_complete=False,original_historical_inputs_changed=False,
        limitation='Some product-level prohibited revenue and complete income breakdowns cannot be established from reviewed public sources. The SEC API does not supply an official Yasaar verdict.')
    save_json(report/'recovery_summary.json',dict(summary=summary,companies=rows))
    text=['# Missing-field recovery and rerun','',
        'Same information cutoff: **31 December 2025**. SEC API snapshots were retrieved on 20 October 2026 and cross-checked to eligible original filings, never used as current historical truth.','',
        f"All {api['api_files']} CompanyFacts downloads succeeded. {api['exact_original_fact_matches']:,} eligible original fact representations matched exactly on concept, accession, period and value.",'',
        '| Result | Before | After |','| --- | ---: | ---: |']
    for key,label in [('passes_research_filters','Complete evidenced pass'),('fails_initial_filters','Fails an initial filter'),('needs_review','Needs further evidence')]:
        text.append(f"| {label} | {before['counts'][key]} | {results['summary']['counts'][key]} |")
    text += ['', '## What was actually recovered','',
        '- Source-bound borrowing components, including Lowe\'s unsecured notes explicitly excluding finance leases.',
        '- Receivable values previously rejected because detailed notes and rounded narrative used different precision. Declared XBRL rounding intervals must intersect; real conflicts stay unknown.',
        '- Interest-bearing security balances, with cash overlap handled explicitly. Apple\'s table requires a subtraction before adding cash; NVIDIA\'s reported securities floor is sufficient without adding cash.',
        '- Separate annual interest income from original report tables for Costco and McDonald\'s, and additional eligible gross-interest concept candidates.',
        '- Microsoft\'s combined interest/dividend figure is retained as combined. Net interest and income mixed with other items remain separate candidates, not invented gross income.','',
        'Field-coverage counts are amounts/candidates found, not proof of complete categories:','',
        '```json',json.dumps(coverage['counts'],indent=2),'```','',
        '## What remains unavailable or unresolved','',
        '**All required fields are not complete.** Some companies do not separately disclose the business/product shares needed for the prohibited-revenue test. Other income is net or combined. An absence in CompanyFacts does not prove absence in a report; the full original annual and latest financial notes were inventoried too. These searches still do not establish every prohibited-income numerator. No absent disclosure was converted to zero.','',
        f"The {results['summary']['counts']['needs_review']} review cases are not halal or haram verdicts. Full source mapping and appropriate review remain necessary before a complete pass or portfolio eligibility. Original/raw data and prediction training data were not altered.",'',
        '| Company | Current result | New result? | Gross-interest candidate found? |','| --- | --- | --- | --- |']
    for r in rows:text.append(f"| {r['ticker']} | {r['current_status']} | {'yes' if r['changed'] else 'no'} | {'yes' if r['separate_gross_interest_candidate'] else 'not established'} |")
    (report/'recovery_summary.md').write_text('\n'.join(text)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
