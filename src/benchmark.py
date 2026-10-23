"""Reproducible five-family comparison; never selects models on test scores."""
import argparse
import json
from pathlib import Path
from time import perf_counter

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (ExtraTreesClassifier, GradientBoostingClassifier,
                              HistGradientBoostingClassifier, RandomForestClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import fbeta_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .ai4i import FEATURES, TARGET, SEED, fit_baseline, metrics


def candidates():
    estimators = {
        'logistic_regression': LogisticRegression(class_weight='balanced', max_iter=2000, random_state=SEED),
        'random_forest': RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
            class_weight='balanced_subsample', random_state=SEED, n_jobs=1),
        'extra_trees': ExtraTreesClassifier(n_estimators=200, min_samples_leaf=2,
            class_weight='balanced', random_state=SEED, n_jobs=1),
        'gradient_boosting': GradientBoostingClassifier(n_estimators=200, learning_rate=.05,
            max_depth=3, min_samples_leaf=5, random_state=SEED),
        'hist_gradient_boosting': HistGradientBoostingClassifier(max_iter=200, learning_rate=.1,
            max_leaf_nodes=15, l2_regularization=1, early_stopping=False, random_state=SEED),
    }
    return {name: make_pipeline(ColumnTransformer([
        ('type', OneHotEncoder(handle_unknown='error', sparse_output=False), ['Type']),
        ('numeric', StandardScaler() if name == 'logistic_regression' else 'passthrough', FEATURES[1:])]),
        estimator) for name, estimator in estimators.items()}


def select_winner(rows):
    return max(rows, key=lambda row: (row['validation']['f2'],
               row['validation']['average_precision'], row['name']))['name']


def compare(path):
    baseline = fit_baseline(path)  # Shared validation, provenance and exact existing split.
    frame = pd.read_csv(path).set_index('UDI')
    splits = baseline.report['split_ids']
    X, y = frame[FEATURES], frame[TARGET].astype(int)
    rows, fitted = [], {}
    for name, model in candidates().items():
        started = perf_counter()
        model.fit(X.loc[splits['train']], y.loc[splits['train']])
        elapsed = perf_counter() - started
        scores = model.predict_proba(X.loc[splits['validation']])[:, 1]
        threshold = max([i / 100 for i in range(5, 96, 5)], key=lambda t:
            (fbeta_score(y.loc[splits['validation']], scores >= t, beta=2, zero_division=0), t))
        rows.append({'name': name, 'threshold': threshold, 'fit_seconds': elapsed,
            'parameters': model.steps[-1][1].get_params(),
            'validation': metrics(y.loc[splits['validation']], scores, threshold)})
        fitted[name] = model
    winner = select_winner(rows)  # Lock selection before examining any test results.
    for row in rows:
        scores = fitted[row['name']].predict_proba(X.loc[splits['test']])[:, 1]
        row['test'] = metrics(y.loc[splits['test']], scores, row['threshold'])
    return {'selected_model': winner, 'selection': 'Validation F2; ties use validation average precision then name',
        'scope': 'Five fixed configurations, not an exhaustive search or universally best models',
        'test_caveat': 'Existing test set was previously inspected; this comparison is exploratory, not a fresh external validation',
        'dataset_sha256': baseline.report['dataset_sha256'], 'rows': len(frame),
        'features': FEATURES, 'seed': SEED, 'sklearn_version': baseline.report['sklearn_version'],
        'split_ids': splits, 'results': rows, 'dummy': baseline.report['most_frequent_baseline'],
        'limitations': baseline.report['limitations'], 'production_model_changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('data/ai4i/ai4i2020.csv'))
    parser.add_argument('--report', type=Path, default=Path('data/ai4i/model-comparison.json'))
    args = parser.parse_args()
    report = compare(args.csv)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'split_ids'}, indent=2))


if __name__ == '__main__':
    main()
