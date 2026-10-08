"""Build audited, session-aligned core features and labels; no screening claims."""
import argparse
from pathlib import Path
import exchange_calendars as xcals
import pandas as pd
from ..features.core import build_features,FEATURES
from ..labels.targets import build_targets,split_and_label
from .reconciliation import save_json,sha256
from .training_inputs import require_audited_prices


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prices',type=Path,required=True)
    p.add_argument('--repo',type=Path,default=Path.cwd());a=p.parse_args()
    calendar=xcals.get_calendar('XNYS',start='2015-01-01',end='2026-12-31').sessions
    calendar=calendar[(calendar>=pd.Timestamp('2016-01-01'))&(calendar<=pd.Timestamp('2025-12-31'))]
    prices=require_audited_prices(pd.read_csv(a.prices))
    features=build_features(prices,calendar)
    targets=build_targets(prices,calendar)
    dataset,cutoffs=split_and_label(features.merge(targets,on=['ticker','as_of_date'],validate='one_to_one'))
    interim=a.repo/'data/interim/readiness_v1';interim.mkdir(parents=True,exist_ok=True)
    processed=a.repo/'data/processed/core_v1_readiness';processed.mkdir(parents=True,exist_ok=True)
    features.to_csv(interim/'feature_rows.csv',index=False)
    dataset.to_csv(interim/'feature_target_audit.csv',index=False)
    used=dataset[dataset.split!='excluded']
    used.to_csv(processed/'research_rows.csv',index=False)
    report=a.repo/'reports/validation/readiness_v1'
    manifest={}
    for name,g in used.groupby('split'):
        manifest[name]=dict(rows=len(g),ticker_count=g.ticker.nunique(),sessions=g.as_of_date.nunique(),
            first_feature_date=str(g.as_of_date.min().date()),last_feature_date=str(g.as_of_date.max().date()),
            label_end_max=str(g.label_end_date.max().date()))
    save_json(report/'label_definitions.json',cutoffs)
    save_json(report/'dataset_manifest.json',dict(calendar_version=xcals.__version__,calendar='XNYS',
        input_sha256=sha256(a.prices),feature_order=FEATURES,splits=manifest,
        eligible_rows=len(used),excluded_rows=len(dataset)-len(used),
        excluded_reasons=dataset.loc[dataset.split=='excluded','exclusion_reason'].value_counts().to_dict(),
        methodology_status='proposed_v1_1_research_not_approved',screening_ready=False,
        unresolved_action_windows_excluded=True))
    calendar.to_series().dt.strftime('%Y-%m-%d').to_csv(report/'exchange_sessions.csv',index=False,header=['session_date'])
    print(manifest)


if __name__=='__main__':main()
