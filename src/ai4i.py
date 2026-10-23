"""AI4I classification experiment; no invented sensor history or maintenance procedure."""
import argparse
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
from typing import Literal
from urllib.request import urlopen
import zipfile

import numpy as np
import pandas as pd
from pydantic import Field
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, confusion_matrix, fbeta_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from .contracts import Contract, MaintenanceProposal, WorkOrder
from .explanation import Selection
from .ledger import Ledger

SOURCE = 'https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset'
DOWNLOAD = 'https://archive.ics.uci.edu/static/public/601/ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset.zip'
EXPECTED_SHA256 = 'dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e'
FEATURES = ['Type', 'Air temperature [K]', 'Process temperature [K]',
            'Rotational speed [rpm]', 'Torque [Nm]', 'Tool wear [min]']
TARGET = 'Machine failure'
SEED = 42
LIMITATIONS = [
    'AI4I is published synthetic data, not measured factory telemetry.',
    'Predicts the dataset machine-failure label at an observation; no future failure horizon is established.',
    'Random stratified holdout is not validation on a new factory, machine fleet, or future time period.',
    'Classifier score is uncalibrated; not a validated real-world failure probability.',
    'No remaining-life labels or approved maintenance manual: RUL unsupported; actions are simulated review only.',
    'Observed inputs are evidence, not causal attribution or proof of a failed component.',
]


class Observation(Contract):
    kind: Literal['L', 'M', 'H'] = Field(alias='Type')
    air: float = Field(alias='Air temperature [K]', gt=0)
    process: float = Field(alias='Process temperature [K]', gt=0)
    speed: float = Field(alias='Rotational speed [rpm]', gt=0)
    torque: float = Field(alias='Torque [Nm]', ge=0)
    wear: float = Field(alias='Tool wear [min]', ge=0)


class DatasetResult(Contract):
    record_id: str
    model_id: str
    score: float | None = Field(ge=0, le=1)
    score_kind: Literal['uncalibrated_classifier_score'] = 'uncalibrated_classifier_score'
    threshold: float
    predicted_failure: bool | None
    observation: Observation
    explanation_mode: Literal['offline', 'bedrock_selection', 'fallback']
    statements: list[str]
    limitations: list[str]
    quality_flags: list[str]
    remaining_life: None = None
    order: WorkOrder | None


@dataclass
class Baseline:
    model: object
    threshold: float
    report: dict
    heldout: pd.DataFrame
    bounds: dict


def download_dataset(destination: Path) -> Path:
    """Explicit opt-in network operation. Never extract arbitrary archive paths."""
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite {destination}')
    with urlopen(DOWNLOAD, timeout=30) as response:
        archive = response.read(5_000_001)
    if len(archive) > 5_000_000:
        raise ValueError('Dataset archive exceeds expected size')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        info = z.getinfo('ai4i2020.csv')
        if info.file_size > 5_000_000:
            raise ValueError('CSV exceeds expected size')
        csv = z.read(info)
    if hashlib.sha256(csv).hexdigest() != EXPECTED_SHA256:
        raise ValueError('UCI content changed; review provenance before accepting a new version')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as out:
        out.write(csv)
    return destination


def metrics(y, scores, threshold):
    predicted = scores >= threshold
    return {'precision': float(precision_score(y, predicted, zero_division=0)),
            'recall': float(recall_score(y, predicted, zero_division=0)),
            'average_precision': float(average_precision_score(y, scores)),
            'f2': float(fbeta_score(y, predicted, beta=2, zero_division=0)),
            'confusion_matrix': confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
            'class_counts': {'nonfailure': int((y == 0).sum()), 'failure': int((y == 1).sum())}}


def fit_baseline(path: str | Path) -> Baseline:
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = pd.read_csv(path)
    required = set(FEATURES + [TARGET, 'UDI'])
    if not required <= set(frame.columns) or frame['UDI'].isna().any() or not frame['UDI'].is_unique:
        raise ValueError('Dataset needs six documented features, binary target and unique UDI')
    if frame[TARGET].isna().any() or set(frame[TARGET].unique()) != {0, 1}:
        raise ValueError('Machine failure must contain both binary classes')
    if frame[TARGET].value_counts().min() < 10:
        raise ValueError('Too few examples for stratified train/validation/test split')
    # Explicit allowlist excludes UDI, Product ID and every failure-mode target.
    X = pd.DataFrame([Observation.model_validate(row).model_dump(by_alias=True)
                      for row in frame[FEATURES].to_dict('records')])
    y = frame[TARGET].astype(int)
    train, rest = train_test_split(frame.index, test_size=0.4, random_state=SEED, stratify=y)
    validation, test = train_test_split(rest, test_size=0.5, random_state=SEED, stratify=y.loc[rest])
    model = make_pipeline(ColumnTransformer([
        ('type', OneHotEncoder(handle_unknown='error', sparse_output=False), ['Type']),
        ('numeric', 'passthrough', FEATURES[1:])]),
        RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                               class_weight='balanced_subsample', random_state=SEED, n_jobs=1))
    model.fit(X.loc[train], y.loc[train])
    valid_scores = model.predict_proba(X.loc[validation])[:, 1]
    candidates = [i / 100 for i in range(5, 96, 5)]
    # Select only on validation; ties choose the higher threshold (fewer alerts).
    threshold = max(candidates, key=lambda t: (fbeta_score(y.loc[validation], valid_scores >= t,
                                                        beta=2, zero_division=0), t))
    test_scores = model.predict_proba(X.loc[test])[:, 1]
    dummy = DummyClassifier(strategy='most_frequent').fit(X.loc[train], y.loc[train])
    bounds = {name: [float(X.loc[train, name].min()), float(X.loc[train, name].max())] for name in FEATURES[1:]}
    outside = np.zeros(len(test), dtype=bool)
    for name, (low, high) in bounds.items():
        outside |= ((X.loc[test, name] < low) | (X.loc[test, name] > high)).to_numpy()
    recipe = f'{digest}|RF200-leaf2-balanced|{SEED}|{threshold}|{sklearn.__version__}'
    report = {'model_id': 'AI4I-RF1-' + hashlib.sha256(recipe.encode()).hexdigest()[:16],
        'dataset_sha256': digest, 'source': SOURCE, 'license': 'CC BY 4.0',
        'matches_verified_uci_download': digest == EXPECTED_SHA256,
        'attribution': 'Stephan Matzka, AI4I 2020 Predictive Maintenance Dataset, UCI, 2020, DOI 10.24432/C5HS5C',
        'rows': len(frame), 'features': FEATURES, 'target': TARGET, 'seed': SEED,
        'sklearn_version': sklearn.__version__, 'threshold': threshold, 'threshold_selected_on': 'validation',
        'threshold_objective': 'Maximum validation F2; fixed grid 0.05..0.95; ties prefer higher threshold',
        'split_ids': {name: frame.loc[indices, 'UDI'].tolist() for name, indices in
                      [('train', train), ('validation', validation), ('test', test)]},
        'validation': metrics(y.loc[validation], valid_scores, threshold),
        'test': metrics(y.loc[test], test_scores, threshold),
        'most_frequent_baseline': metrics(y.loc[test], dummy.predict_proba(X.loc[test])[:, 1], 0.5),
        'test_metric_scope': 'Raw classifier on all test rows; runtime additionally abstains outside training ranges',
        'runtime_test_abstentions': int(outside.sum()),
        'remaining_useful_life': None, 'limitations': LIMITATIONS}
    return Baseline(model, threshold, report, frame.loc[test].copy(), bounds)


def run_record(bundle: Baseline, raw: dict, record_id: str, ledger_path: str | Path, *, provider=None) -> DatasetResult:
    observation = Observation.model_validate(raw)
    values = observation.model_dump(by_alias=True)
    flags = [f'{name} outside training range [{low:g}, {high:g}]'
             for name, (low, high) in bundle.bounds.items() if not low <= values[name] <= high]
    score = None if flags else float(bundle.model.predict_proba(pd.DataFrame([values]))[0, 1])
    predicted = None if score is None else score >= bundle.threshold
    model_id = bundle.report['model_id']
    identity = json.dumps([model_id, record_id, values], sort_keys=True)
    assessment_id = hashlib.sha256(identity.encode()).hexdigest()
    facts = {
        'prediction': 'Assessment abstained: input outside training range.' if score is None else
            f'Classifier score {score:.4f}; validation-selected threshold {bundle.threshold:.2f}; predicted class {int(predicted)}.',
        'thermal': f'Observed air {observation.air:g} K; process {observation.process:g} K.',
        'mechanical': f'Observed rotation {observation.speed:g} rpm; torque {observation.torque:g} Nm.',
        'wear': f'Observed tool wear {observation.wear:g} minutes; product type {observation.kind}.'}
    selected, mode = list(facts), 'offline'
    if provider is not None and not flags:
        try:
            output = provider.generate({'assessment_id': assessment_id, 'risk_band': 'review' if predicted else 'below_threshold',
                'evidence': [{'evidence_id': key, 'fact': fact, 'breached': key == 'prediction'} for key, fact in facts.items()]})
            ids = Selection.model_validate_json(output).evidence_ids
            if len(set(ids)) != len(ids) or not set(ids) <= facts.keys() or 'prediction' not in ids:
                raise ValueError('Unknown or incomplete evidence selection')
            selected, mode = ids, 'bedrock_selection'
        except Exception:
            mode = 'fallback'
    review = predicted is not False
    proposal = MaintenanceProposal(assessment_id=assessment_id, asset_id=f'AI4I-RECORD-{record_id}',
        action='review' if review else 'none', review_required=review,
        reason='Simulated technician review: no verified asset manual, failure cause, part or slot.' if review else
               'Below experimental classifier threshold; this is not a declaration that equipment is safe.')
    order = Ledger(ledger_path).simulate(proposal)
    return DatasetResult(record_id=record_id, model_id=model_id, score=score, threshold=bundle.threshold,
        predicted_failure=predicted, observation=observation, explanation_mode=mode,
        statements=[f'{facts[key]} [AI4I:{record_id}:{key}]' for key in selected],
        limitations=LIMITATIONS, quality_flags=flags, order=order)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('data/ai4i/ai4i2020.csv'))
    parser.add_argument('--download', action='store_true', help='Explicitly download the public UCI CSV if absent')
    parser.add_argument('--report', type=Path, default=Path('data/ai4i/evaluation.json'))
    args = parser.parse_args()
    if args.download and not args.csv.exists():
        download_dataset(args.csv)
    bundle = fit_baseline(args.csv)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(bundle.report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in bundle.report.items() if key != 'split_ids'}, indent=2))


if __name__ == '__main__':
    main()
