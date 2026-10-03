"""Make a readable review index without approving company activity or income."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--output-version',default='sec_2015_2025_v2')
    args=parser.parse_args()
    if not __import__('re').fullmatch(r'[A-Za-z0-9_-]+',args.output_version):parser.error('Invalid version')
    report=args.repo/'reports/validation/screening_evidence'/args.output_version
    coverage=json.loads((report/'coverage.json').read_text())
    latest={}
    with (args.repo/'data/interim/screening_evidence'/args.output_version/'business_evidence.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row=json.loads(line)
            if not row.get('text') or row.get('source_issuer_role')!='study_issuer':continue
            if not row.get('available_from_session') or row['available_from_session']>coverage['as_of_date']:continue
            ticker=row['ticker']
            if ticker not in latest or row['filing_date']>latest[ticker]['filing_date']:latest[ticker]=row
    lines=['# Screening evidence review index','',
        'These are source candidates. No company is approved for portfolio entry. Standard and edition remain undecided.','',
        'Counts below are individual source records across years, with duplicate representations and overlapping periods retained. They are not income totals or complete annual coverage.','',
        '| Company | Annual / quarterly reports | Business excerpts | Separate gross interest candidates | Revenue records with business/product dimensions | Latest business filing |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    for row in coverage['companies']:
        b=latest.get(row['ticker']);link=f"[{b['filing_date']}]({b['source_url']})" if b else 'Manual extraction needed'
        lines.append(f"| {row['ticker']} | {row['annual_reports_downloaded']} / {row['quarterly_reports_downloaded']} | {row['business_sections_extracted']} | {row['usable_candidates_by_kind'].get('gross_interest_income_candidate',0)} | {row['business_revenue_dimension_candidates']} | {link} |")
    lines.extend(['','## How to review','',
        'Open the linked original report. Check the business description, revenue notes and income notes against your selected standard. The original source archive retains all collected reports, not just these latest excerpts.','',
        'A zero candidate count means a separate gross figure was not established by this extractor; it does not mean zero income. Combined or net income cannot automatically replace a separate gross amount. Broad segment revenue cannot automatically establish a prohibited-product percentage.','',
        'Record the standard/version, screening date, original fact IDs, compatible reporting periods, approved mappings, known missing disclosures and reviewer identity. Keep unknown amounts empty and return needs_review or insufficient_data.','',
        '## Latest business excerpt openings','',
        'Short openings help locate the business section. They are not complete activity classifications.'])
    for ticker,b in sorted(latest.items()):
        opening=' '.join(b['text'][:550].split())
        lines.extend(['',f"### {ticker} — {b['filing_date']}",'',opening,'',
            f"Source: [original report]({b['source_url']}). Available from {b['available_from_session']}. Rule: {b.get('extraction_rule')}"])
    (report/'review_index.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Review index:',len(latest),'companies; no screening verdicts generated')


if __name__=='__main__':main()
