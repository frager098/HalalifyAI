"""Train documented candidates on train, select on validation; never inspect test."""
import argparse
import itertools
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score,accuracy_score,balanced_accuracy_score,confusion_matrix,classification_report,log_loss
from threadpoolctl import threadpool_limits
from ..features.core import FEATURES
from ..data.reconciliation import save_json,sha256

CLASSES=['low','medium','high']


def candidates():
    for c in [.1,1,10]:
        yield 'LR',dict(C=c,max_iter=2000,solver='lbfgs',random_state=42),lambda params:make_pipeline(StandardScaler(),LogisticRegression(**params))
    for depth,leaf in itertools.product([6,12],[20,50]):
        yield 'RF',dict(n_estimators=300,max_features='sqrt',max_depth=depth,min_samples_leaf=leaf,random_state=42,n_jobs=2),lambda params:RandomForestClassifier(**params)
    for leaves,iters in itertools.product([7,15],[100,200]):
        yield 'HGB',dict(learning_rate=.05,min_samples_leaf=30,l2_regularization=1,early_stopping=False,max_leaf_nodes=leaves,max_iter=iters,random_state=42),lambda params:HistGradientBoostingClassifier(**params)


def metrics(truth,prediction,probabilities=None):
    result=dict(macro_f1=float(f1_score(truth,prediction,labels=CLASSES,average='macro',zero_division=0)),
        accuracy=float(accuracy_score(truth,prediction)),balanced_accuracy=float(balanced_accuracy_score(truth,prediction)),
        confusion_matrix=confusion_matrix(truth,prediction,labels=CLASSES).tolist(),
        per_class=classification_report(truth,prediction,labels=CLASSES,output_dict=True,zero_division=0))
    if probabilities is not None:
        if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1),1,atol=1e-6):
            raise ValueError('Invalid probabilities')
        alphabetical=sorted(CLASSES)
        result['log_loss']=float(log_loss(truth,probabilities[:,[CLASSES.index(x) for x in alphabetical]],labels=alphabetical))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--repo',type=Path,default=Path.cwd())
    a=p.parse_args();f=pd.read_csv(a.dataset)
    train=f[f.split=='train'];val=f[f.split=='validation']
    if train.empty or val.empty:raise ValueError('Training/validation partitions required')
    if not train.label_end_date.max()<val.as_of_date.min():raise ValueError('Chronological leakage')
    if not np.isfinite(train[FEATURES]).all().all() or not np.isfinite(val[FEATURES]).all().all():raise ValueError('Missing/nonfinite core inputs')
    thresholds=json.loads((a.repo/'reports/validation/readiness_v1/label_definitions.json').read_text())
    output=a.repo/'reports/experiments/core_v1_readiness';output.mkdir(parents=True,exist_ok=True)
    artifacts=a.repo/'artifacts/core_v1_readiness';artifacts.mkdir(parents=True,exist_ok=True)
    results={}
    with threadpool_limits(limits=2):
        for target,numeric,historical in [('return_class','future_return_20d','ret_20d'),('risk_class','future_volatility_20d','vol_20d')]:
            counts=train[target].value_counts()
            majority=max(CLASSES,key=lambda x:counts.get(x,0))
            boundaries=thresholds[numeric]
            historical_pred=np.where(val[historical]<=boundaries['lower_cutoff'],'low',np.where(val[historical]<=boundaries['upper_cutoff'],'medium','high'))
            baselines=dict(majority=metrics(val[target],[majority]*len(val)),historical=metrics(val[target],historical_pred))
            records=[];best_score=-1;fitted=[]
            for family,params,factory in candidates():
                model=factory(params);model.fit(train[FEATURES],train[target])
                probabilities=model.predict_proba(val[FEATURES])[:,[list(model.classes_).index(x) for x in CLASSES]]
                predicted=np.array(CLASSES)[np.argmax(probabilities,axis=1)]
                result=dict(family=family,parameters=params,metrics=metrics(val[target],predicted,probabilities))
                records.append(result);fitted.append(model)
                print(target,family,params,'validation macro-F1',result['metrics']['macro_f1'],flush=True)
            best_score=max(r['metrics']['macro_f1'] for r in records)
            tied=[i for i,r in enumerate(records) if best_score-r['metrics']['macro_f1']<.01]
            chosen=min(tied,key=lambda i:({'LR':0,'RF':1,'HGB':2}[records[i]['family']],-records[i]['metrics']['macro_f1'],i))
            path=artifacts/(target+'.joblib');joblib.dump(fitted[chosen],path)
            results[target]=dict(baselines=baselines,candidates=records,selected=records[chosen],
                model_artifact=str(path),artifact_sha256=sha256(path),feature_names=FEATURES,
                thresholds=boundaries,seed=42,probability_calibration='uncalibrated',
                train_rows=len(train),validation_rows=len(val),test_evaluated=False,
                dataset_sha256=sha256(a.dataset),
                methodology_status='proposed_research_not_approved',screening_ready=False)
            save_json(output/(target+'.json'),results[target])
    save_json(output/'model_comparison.json',results)
    print('Validation selection complete. Test metrics were not calculated.')


if __name__=='__main__':main()
