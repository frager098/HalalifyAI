"""Rebuild data and refit selected configurations without scoring test rows."""
import argparse
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from ..features.core import FEATURES
from ..models.train_candidates import candidates, metrics, CLASSES
from ..data.reconciliation import save_json, sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd());a=p.parse_args();repo=a.repo.resolve()
    source=repo/'data/processed/core_v1_readiness/research_rows.csv'
    expected=pd.read_csv(source)
    with tempfile.TemporaryDirectory(prefix='halalify-reproduce-') as folder:
        subprocess.run([sys.executable,'-m','src.data.build_research_dataset',
            '--prices',str(repo/'data/interim/readiness_v1/audited_prices.csv'),
            '--repo',folder],check=True,cwd=repo)
        rebuilt=pd.read_csv(Path(folder)/'data/processed/core_v1_readiness/research_rows.csv')
        pd.testing.assert_frame_equal(expected,rebuilt,check_exact=True)
    train=expected[expected.split=='train'];val=expected[expected.split=='validation']
    comparison=json.loads((repo/'reports/experiments/core_v1_readiness/model_comparison.json').read_text())
    checked={}
    with threadpool_limits(limits=2):
        for target,result in comparison.items():
            selected=result['selected']
            factory=next(factory for family,params,factory in candidates()
                if family==selected['family'] and params==selected['parameters'])
            model=factory(selected['parameters']);model.fit(train[FEATURES],train[target])
            actual=model.predict_proba(val[FEATURES])[:,[list(model.classes_).index(c) for c in CLASSES]]
            saved=joblib.load(repo/'artifacts/core_v1_readiness'/f'{target}.joblib')
            original=saved.predict_proba(val[FEATURES])[:,[list(saved.classes_).index(c) for c in CLASSES]]
            np.testing.assert_allclose(actual,original,atol=1e-12,rtol=1e-12)
            score=metrics(val[target],np.array(CLASSES)[actual.argmax(axis=1)],actual)
            if abs(score['macro_f1']-selected['metrics']['macro_f1'])>1e-12:
                raise ValueError('Validation score did not reproduce')
            checked[target]=dict(validation_macro_f1=score['macro_f1'],probabilities_match=True)
            print(target,'selected configuration reproduced',flush=True)
    save_json(repo/'reports/validation/readiness_v1/reproducibility.json',dict(
        python=sys.version,python_executable=sys.executable,isolated_environment=sys.prefix!=sys.base_prefix,
        dataset_sha256=sha256(source),all_rebuilt_dataset_values_match=True,
        selected_models=checked,test_evaluated=False,
        scope='Selected configurations reproduced; complete candidate grid not rerun here'))


if __name__=='__main__':main()
