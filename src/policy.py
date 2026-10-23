"""Selectable operating policies over the fixed AI4I recipe.

Three usable policies share the existing seed-42 split, six-feature allowlist, and
the 0.05..0.95 validation-F2 threshold grid: the verified random forest, ordinary
gradient boosting, and a hybrid that averages their probabilities with a weight
chosen on validation only. Every policy carries a distinct model identity that
embeds its recipe, weight, and threshold so cached explanations and ledger
idempotency keys can never confuse one model for another. No policy alters the
score it reports or performs a real action; selection never looks at test scores.
"""
import hashlib
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import average_precision_score, fbeta_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from .ai4i import FEATURES, SEED, TARGET, metrics

POLICIES = ('random_forest', 'gradient_boosting', 'hybrid_rf_gb')
HYBRID_WEIGHTS = [0.25, 0.5, 0.75]
THRESHOLD_GRID = [i / 100 for i in range(5, 96, 5)]

# Fixed recipe fragments; identical configuration to the five-model benchmark so
# a policy and the benchmark agree exactly.
_RECIPES = {
    'random_forest': 'RF200-leaf2-balanced',
    'gradient_boosting': 'GB200-lr0.05-depth3-leaf5',
}
_PREFIX = {'random_forest': 'AI4I-RF', 'gradient_boosting': 'AI4I-GB', 'hybrid_rf_gb': 'AI4I-HYB'}


def _estimator(name):
    if name == 'random_forest':
        return RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
            class_weight='balanced_subsample', random_state=SEED, n_jobs=1)
    if name == 'gradient_boosting':
        return GradientBoostingClassifier(n_estimators=200, learning_rate=.05,
            max_depth=3, min_samples_leaf=5, random_state=SEED)
    raise ValueError(f'Unknown base estimator {name!r}')


def _pipeline(name):
    return make_pipeline(ColumnTransformer([
        ('type', OneHotEncoder(handle_unknown='error', sparse_output=False), ['Type']),
        ('numeric', 'passthrough', FEATURES[1:])]), _estimator(name))


def _select_threshold(y_valid, valid_scores):
    """Maximise validation F2 over the fixed grid; ties prefer the higher threshold."""
    return max(THRESHOLD_GRID, key=lambda t: (
        fbeta_score(y_valid, valid_scores >= t, beta=2, zero_division=0), t))


@dataclass
class Policy:
    name: str
    model_id: str
    recipe: str
    threshold: float
    weight: float | None
    report: dict
    _bases: dict = field(repr=False, default_factory=dict)

    def base_scores(self, base_name: str, X: pd.DataFrame) -> np.ndarray:
        return self._bases[base_name].predict_proba(X[FEATURES])[:, 1]

    def scores(self, X: pd.DataFrame) -> np.ndarray:
        if self.weight is None:
            # Single-estimator policy.
            (only,) = self._bases.values()
            return only.predict_proba(X[FEATURES])[:, 1]
        rf = self.base_scores('random_forest', X)
        gb = self.base_scores('gradient_boosting', X)
        return self.weight * rf + (1 - self.weight) * gb

    def score_row(self, values: dict) -> float:
        return float(self.scores(pd.DataFrame([values]))[0])


def _identity(name, recipe, digest, threshold):
    full = f'{digest}|{recipe}|{SEED}|{threshold}|{sklearn.__version__}'
    return _PREFIX[name] + '-' + hashlib.sha256(full.encode()).hexdigest()[:16]


def build_policy(name: str, path, baseline) -> Policy:
    """Fit base models on the existing training split only and freeze the
    operating point on validation before any test evaluation."""
    if name not in POLICIES:
        raise ValueError(f'Unknown policy {name!r}')
    digest = baseline.report['dataset_sha256']
    splits = baseline.report['split_ids']
    frame = pd.read_csv(path).set_index('UDI')
    X, y = frame[FEATURES], frame[TARGET].astype(int)
    train, validation = splits['train'], splits['validation']
    y_valid = y.loc[validation]

    if name in ('random_forest', 'gradient_boosting'):
        started = perf_counter()
        model = _pipeline(name).fit(X.loc[train], y.loc[train])
        fit_seconds = perf_counter() - started
        valid_scores = model.predict_proba(X.loc[validation])[:, 1]
        threshold = _select_threshold(y_valid, valid_scores)
        recipe = _RECIPES[name]
        model_id = _identity(name, recipe, digest, threshold)
        report = {'name': name, 'model_id': model_id, 'recipe': recipe, 'threshold': threshold,
                  'weight': None, 'fit_seconds': fit_seconds, 'threshold_selected_on': 'validation',
                  'validation': metrics(y_valid, valid_scores, threshold)}
        return Policy(name=name, model_id=model_id, recipe=recipe, threshold=threshold,
                      weight=None, report=report, _bases={name: model})

    # Hybrid: fit both bases on train only, then search weight x threshold on validation.
    bases, base_valid = {}, {}
    fit_seconds = 0.0
    for base in ('random_forest', 'gradient_boosting'):
        started = perf_counter()
        model = _pipeline(base).fit(X.loc[train], y.loc[train])
        fit_seconds += perf_counter() - started
        bases[base] = model
        base_valid[base] = model.predict_proba(X.loc[validation])[:, 1]

    search = []
    for weight in HYBRID_WEIGHTS:
        blended = weight * base_valid['random_forest'] + (1 - weight) * base_valid['gradient_boosting']
        threshold = _select_threshold(y_valid, blended)
        search.append({'weight': weight, 'threshold': threshold,
                       'validation_f2': float(fbeta_score(y_valid, blended >= threshold, beta=2, zero_division=0)),
                       'validation_average_precision': float(average_precision_score(y_valid, blended))})
    # Freeze the weight/threshold on validation; ties prefer higher AP then higher threshold.
    best = max(search, key=lambda e: (e['validation_f2'], e['validation_average_precision'], e['threshold']))
    weight, threshold = best['weight'], best['threshold']
    recipe = f'HYB-RF-GB-w{weight}-t{threshold}'
    model_id = _identity('hybrid_rf_gb', recipe, digest, threshold)
    blended_valid = weight * base_valid['random_forest'] + (1 - weight) * base_valid['gradient_boosting']
    report = {'name': 'hybrid_rf_gb', 'model_id': model_id, 'recipe': recipe, 'threshold': threshold,
              'weight': weight, 'fit_seconds': fit_seconds,
              'threshold_selected_on': 'validation', 'weight_selected_on': 'validation',
              'weight_grid': HYBRID_WEIGHTS, 'weight_search': search,
              'validation': metrics(y_valid, blended_valid, threshold)}
    return Policy(name='hybrid_rf_gb', model_id=model_id, recipe=recipe, threshold=threshold,
                  weight=weight, report=report, _bases=bases)


def compare_policies(path, baseline) -> dict:
    """Validation-selected operating points for all three policies, with test
    metrics computed only after each selection is frozen."""
    frame = pd.read_csv(path).set_index('UDI')
    X, y = frame[FEATURES], frame[TARGET].astype(int)
    test = baseline.report['split_ids']['test']
    policies = {name: build_policy(name, path, baseline) for name in POLICIES}
    out = {}
    for name, policy in policies.items():
        test_scores = policy.scores(X.loc[test])
        entry = {'model_id': policy.model_id, 'recipe': policy.recipe, 'weight': policy.weight,
                 'threshold': policy.threshold, 'fit_seconds': policy.report['fit_seconds'],
                 'validation': policy.report['validation'],
                 'test': metrics(y.loc[test], test_scores, policy.threshold)}
        if name == 'hybrid_rf_gb':
            entry['weight_search'] = policy.report['weight_search']
        out[name] = entry
    return {'policies': out, 'hybrid_weight': policies['hybrid_rf_gb'].weight,
            'hybrid_threshold': policies['hybrid_rf_gb'].threshold,
            'dataset_sha256': baseline.report['dataset_sha256'], 'rows': len(frame),
            'features': FEATURES, 'seed': SEED, 'sklearn_version': sklearn.__version__,
            'selection_scope': ('Three fixed policies; weight from [0.25,0.5,0.75] and threshold from the '
                                '0.05..0.95 grid chosen by validation F2 only, never on test scores.'),
            'test_caveat': ('The existing test set was previously inspected; this comparison is exploratory, '
                            'not a fresh external validation, and does not establish that any policy is best.'),
            'production_model_changed': False}


def explorer_zones(observation: dict) -> list[dict]:
    """Map the six allowlisted observations to three illustrative machine zones.

    Values come only from the supplied record. Zones report observed readings as
    evidence; they never attribute the machine-level classifier to a component or
    invent a fault state.
    """
    def g(key):
        value = observation[key]
        return f'{value:g}' if isinstance(value, (int, float)) else str(value)

    return [
        {'id': 'drive', 'label': 'Drive / spindle',
         'observations': [f'Rotational speed {g("Rotational speed [rpm]")} rpm',
                          f'Torque {g("Torque [Nm]")} Nm',
                          f'Product type {g("Type")}']},
        {'id': 'process_chamber', 'label': 'Process chamber',
         'observations': [f'Air temperature {g("Air temperature [K]")} K',
                          f'Process temperature {g("Process temperature [K]")} K']},
        {'id': 'tool_head', 'label': 'Tool head',
         'observations': [f'Tool wear {g("Tool wear [min]")} min']},
    ]
