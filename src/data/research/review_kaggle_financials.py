"""Inspect the downloaded Figurewell SEC candidate without joining its values.

Current-provider dates, missing categories and condensed tag mappings must not
silently replace original historical issuer facts.
"""
import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import pyarrow.parquet as pq

from ..reconciliation import COMPANY_SYMBOLS, save_json, sha256


def review(archive, notes, out, cutoff='2025-12-31'):
    with ZipFile(archive) as z:
        meta=json.loads(z.read('meta.json'))
        metrics=pd.read_csv(io.BytesIO(z.read('key_metrics.csv')),dtype={'cik':'string','adsh':'string'})
        facts=pq.ParquetFile(io.BytesIO(z.read('facts.parquet')))
        selected={}
        issuer_tickers={}
        for ticker in COMPANY_SYMBOLS:
            packet=json.loads((Path(notes)/(ticker+'.json')).read_text())
            for role, original in packet.items():
                issuer_tickers[original['cik'].lstrip('0')]=ticker
                selected[original['accession_number'].replace('-','')]=(ticker,role,original)
        target=metrics[metrics.cik.str.lstrip('0').isin(issuer_tickers)].copy()
        target['study_ticker']=target.cik.str.lstrip('0').map(issuer_tickers)
        eligible=target[target.filed_date.le(cutoff) & target.period_end.le(cutoff)]
        selected_ids=set(selected)
        available_ids=set(eligible.adsh.str.replace('-','',regex=False))
        inventory={}
        columns=[c for c in ['adsh','tag','period_end','duration_quarters','uom','value','taxonomy'] if c in facts.schema_arrow.names]
        for batch in facts.iter_batches(batch_size=100000,columns=columns):
            df=batch.to_pandas()
            if not {'adsh','tag'}.issubset(df):
                raise ValueError('Unexpected candidate schema: cannot check original filings')
            accession=df.adsh.astype(str).str.replace('-','',regex=False)
            keep=accession.isin(selected_ids & available_ids) & df.tag.str.contains('Interest.*Income|Income.*Interest|FinanceLeaseLiability',case=False,regex=True)
            for _,row in df.loc[keep].iterrows():
                key=str(row.adsh).replace('-','')
                ticker,role,original=selected[key]
                inventory.setdefault(ticker,[]).append(dict(role=role,accession_number=original['accession_number'],
                    concept=str(row.tag),value=str(row.get('value')),unit=str(row.get('uom')),
                    period_end=str(row.get('period_end')),quarter_count=str(row.get('duration_quarters')),
                    status='candidate_only_original_context_and_income_definition_review_required'))
        result=dict(source_url='https://www.kaggle.com/datasets/cybermaxtools/figurewell-sec-xbrl-financials',
            archive_sha256=sha256(archive),publisher_metadata=meta,columns=list(metrics.columns),
            facts_schema=facts.schema_arrow.names,key_metric_rows=len(metrics),
            study_company_rows=len(target),study_companies=int(target.study_ticker.nunique()),
            missing_company_tickers=sorted(set(COMPANY_SYMBOLS)-set(target.study_ticker)),
            study_filing_date_min=target.filed_date.min(),study_filing_date_max=target.filed_date.max(),
            eligible_study_rows=len(eligible),cutoff=cutoff,
            original_selected_accessions_present=len(selected_ids & available_ids),
            gross_interest_key_metric_available=any(c in metrics.columns for c in ['interest_income','gross_interest_income']),
            prohibited_product_revenue_key_metric_available=False,
            used_for_decisions=False,used_for_model_training=False,
            reasons=['Rolling four-quarter SEC snapshot is not the 2016–2025 training history.',
                'Key metrics have no complete prohibited-income/product-revenue fields.',
                'Contains filings unavailable at the 2025 cutoff; do not select latest globally.',
                'Underlying SEC source overlaps our retained originals; more rows do not prove complete screening categories.'],
            interest_and_lease_candidates=inventory)
        save_json(out,result)
        print(json.dumps({k:v for k,v in result.items() if k not in ['interest_and_lease_candidates','publisher_metadata']},indent=2))
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--notes',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();review(args.archive,args.notes,args.out)
