"""Dated candidate evidence and explicit missing fields for a not-yet-selected screen."""
import argparse
import json
from pathlib import Path
import pandas as pd
from .reconciliation import COMPANY_SYMBOLS,save_json,sha256

REQUIRED_REVIEW_FIELDS=['total_assets','total_debt','cash_and_cash_equivalents',
    'interest_bearing_securities','accounts_receivable','revenue_ttm',
    'restricted_activity_income','interest_income','total_income_for_screen','direct_prohibited_activity']


def handoff(facts,as_of):
    f=facts.copy()
    f['available_from_session']=pd.to_datetime(f.available_from_session,errors='coerce')
    f['period_end']=pd.to_datetime(f.period_end,errors='coerce')
    f=f[(f.available_from_session<=pd.Timestamp(as_of))&(f.period_end<=pd.Timestamp(as_of))]
    outputs=[]
    for ticker in COMPANY_SYMBOLS:
        g=f[f.ticker==ticker]
        candidates={}
        for name,part in g.groupby('metric_name'):
            # Keep latest available versions within each tag and period. Different
            # tags/components remain separate; no guesses about totals or overlap.
            latest_period=part.period_end.max()
            part=part[part.period_end==latest_period]
            selected=[]
            for _,tag_rows in part.groupby(['source_tag','period_start'],dropna=False):
                tag_rows=tag_rows[tag_rows.available_from_session==tag_rows.available_from_session.max()]
                selected.extend(tag_rows.drop_duplicates('fact_id').to_dict('records'))
            candidates[name]=selected
        outputs.append(dict(ticker=ticker,as_of_date=as_of,
            screening_status='needs_review',profile_review_status='not_selected',
            portfolio_eligible=False,approved_metrics={name:None for name in REQUIRED_REVIEW_FIELDS},
            evidence_candidates=candidates,
            reasons=['Screening standard/edition not selected',
                'Candidate tags require issuer-specific mapping and scope review',
                'Business/prohibited-income and interest-bearing-security evidence not established',
                'Debt totals and compatible TTM periods are not certified']))
    return outputs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--facts',type=Path,required=True);p.add_argument('--as-of',default='2025-12-31')
    p.add_argument('--repo',type=Path,default=Path.cwd());a=p.parse_args()
    facts=pd.read_csv(a.facts,keep_default_na=True,low_memory=False)
    records=handoff(facts,a.as_of)
    # pandas timestamps and NaN are serialized intentionally as ISO dates/null.
    serial=json.loads(pd.Series(records).to_json(date_format='iso'))
    records=list(serial.values())
    target=a.repo/'data/interim/readiness_v1';target.mkdir(parents=True,exist_ok=True)
    save_json(target/'screening_evidence_handoff.json',dict(as_of_date=a.as_of,companies=records,
        source_sha256=sha256(a.facts),standard_not_selected=True))
    save_json(a.repo/'reports/validation/readiness_v1/screening_readiness.json',dict(
        companies=len(records),portfolio_eligible=0,standard_not_selected=True,
        missing_or_unapproved_fields=REQUIRED_REVIEW_FIELDS,
        candidate_presence_by_ticker={r['ticker']:list(r['evidence_candidates']) for r in records},
        next_review='Select standard and edition, then map exact business/income/debt/security components with sources'))
    print('Prepared 50 dated evidence packs. No compliant verdict or invented missing amounts.')


if __name__=='__main__':main()
