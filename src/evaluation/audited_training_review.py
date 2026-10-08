"""Refit frozen validation-selected classifiers and report retrospective test results.

Never choose or tune a model using test results. The test period was seen in
earlier team work and must not be described as a new untouched holdout.
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from ..data.reconciliation import save_json, sha256
from ..features.core import FEATURES
from ..models.train_candidates import CLASSES, candidates, metrics


def validate_partitions(frame):
    if frame.duplicated(['ticker', 'as_of_date']).any():
        raise ValueError('Duplicate company/date observations')
    parts = {name: frame.loc[frame.split.eq(name)].copy()
             for name in ['train', 'validation', 'test']}
    for name, part in parts.items():
        if part.empty or not np.isfinite(part[FEATURES]).all().all():
            raise ValueError(f'Invalid {name} inputs')
        for target in ['return_class', 'risk_class']:
            if not part[target].isin(CLASSES).all():
                raise ValueError(f'Invalid {target} labels')
        part['as_of_date'] = pd.to_datetime(part.as_of_date, errors='raise')
        part['label_end_date'] = pd.to_datetime(part.label_end_date, errors='raise')
        if not part.label_end_date.gt(part.as_of_date).all():
            raise ValueError('Targets must follow prediction dates')
    for first, second in [('train', 'validation'), ('validation', 'test')]:
        if parts[first].label_end_date.max() >= parts[second].as_of_date.min():
            raise ValueError('Future target crosses partition boundary')
    return parts


def baseline_predictions(train, test, target, historical, boundaries):
    counts = train[target].value_counts()
    majority = max(CLASSES, key=lambda c: counts.get(c, 0))
    history = np.where(test[historical] <= boundaries['lower_cutoff'], 'low',
                       np.where(test[historical] <= boundaries['upper_cutoff'], 'medium', 'high'))
    return {'training_majority': np.repeat(majority, len(test)),
            'previous_20_sessions': history}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    comparison_path = repo / 'reports/experiments/core_v1_readiness/model_comparison.json'
    frozen = json.loads(comparison_path.read_text())
    dataset_hash = sha256(args.dataset)
    if any(record['dataset_sha256'] != dataset_hash for record in frozen.values()):
        raise ValueError('Dataset differs from frozen validation selection')
    parts = validate_partitions(pd.read_csv(args.dataset))
    train, val, test = (parts[name] for name in ['train', 'validation', 'test'])
    out = repo / 'reports/experiments/audited_training_review_20261008'
    artifacts = repo / 'artifacts/audited_training_review_20261008'
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {'dataset_sha256': dataset_hash, 'selection_sha256': sha256(comparison_path),
              'fit_scope': 'initial_training_only', 'evaluation': 'retrospective_2023_2025',
              'test_used_for_selection': False, 'probabilities': 'uncalibrated',
              'rows': {name: len(part) for name, part in parts.items()}, 'targets': {}}
    with threadpool_limits(limits=2):
        for target, historical in [('return_class', 'ret_20d'), ('risk_class', 'vol_20d')]:
            record = frozen[target]
            chosen = record['selected']
            factory = next(factory for family, params, factory in candidates()
                           if family == chosen['family'] and params == chosen['parameters'])
            model = factory(chosen['parameters'])
            model.fit(train[FEATURES], train[target])
            def predict(part):
                proba = model.predict_proba(part[FEATURES])[:,
                    [list(model.classes_).index(c) for c in CLASSES]]
                return np.array(CLASSES)[proba.argmax(axis=1)], proba
            val_pred, val_proba = predict(val)
            reproduced = metrics(val[target], val_pred, val_proba)
            if abs(reproduced['macro_f1'] - chosen['metrics']['macro_f1']) > 1e-10:
                raise ValueError('Frozen validation score did not reproduce')
            predictions, probabilities = predict(test)
            baselines = baseline_predictions(train, test, target, historical, record['thresholds'])
            model_path = artifacts / f'{target}.joblib'
            joblib.dump(model, model_path)
            dates = sorted(test.as_of_date.unique())
            # A shared 20-session anchor schedule reduces overlapping targets.
            anchors = test.as_of_date.isin(dates[::20]).to_numpy()
            result = {'selected': chosen, 'validation_reproduced': reproduced,
                      'test': metrics(test[target], predictions, probabilities),
                      'baselines': {name: metrics(test[target], values) for name, values in baselines.items()},
                      'non_overlapping_anchors': {'rows': int(anchors.sum()),
                          'model': metrics(test.loc[anchors, target], predictions[anchors]),
                          'baselines': {name: metrics(test.loc[anchors, target], values[anchors])
                                        for name, values in baselines.items()}},
                      'yearly': {}, 'model_sha256': sha256(model_path)}
            for year in sorted(test.as_of_date.dt.year.unique()):
                mask = test.as_of_date.dt.year.eq(year).to_numpy()
                result['yearly'][str(year)] = {'rows': int(mask.sum()),
                    'model': metrics(test.loc[mask, target], predictions[mask]),
                    'baselines': {name: metrics(test.loc[mask, target], values[mask])
                                  for name, values in baselines.items()}}
            out.mkdir(parents=True, exist_ok=True)
            table = test[['ticker', 'as_of_date', target]].copy()
            table['model_prediction'] = predictions
            for name, values in baselines.items():
                table[name] = values
            table.to_csv(out / f'{target}_predictions.csv', index=False)
            report['targets'][target] = result
            print(target, 'retrospective accuracy', result['test']['accuracy'],
                  'macro-F1', result['test']['macro_f1'], flush=True)
    save_json(out / 'results.json', report)


if __name__ == '__main__':
    main()
