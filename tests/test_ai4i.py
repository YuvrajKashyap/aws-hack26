"""Protect against target leakage, misleading evaluation and unsafe actions."""
import importlib.util
import json
import pandas as pd
import pytest

pytest.importorskip('sklearn', reason='Install requirements-ml.txt for dataset tests')


def api():
    assert importlib.util.find_spec('src.ai4i') is not None, 'AI4I baseline not implemented'
    from src import ai4i
    return ai4i


@pytest.fixture
def dataset(tmp_path):
    rows = []
    for i in range(300):
        failure = int(i % 5 == 0)
        rows.append({'UDI': i + 1, 'Product ID': f'L{i}', 'Type': 'L',
            'Air temperature [K]': 300 + (i % 7) / 10,
            'Process temperature [K]': 310 + (i % 7) / 10,
            'Rotational speed [rpm]': 1500 + i % 20,
            'Torque [Nm]': 80 if failure else 30,
            'Tool wear [min]': i % 200, 'Machine failure': failure,
            'TWF': failure, 'HDF': failure, 'PWF': failure, 'OSF': failure, 'RNF': failure})
    path = tmp_path / 'fixture.csv'
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_split_is_disjoint_and_targets_never_enter_estimator(dataset):
    a = api()
    bundle = a.fit_baseline(dataset)
    splits = bundle.report['split_ids']
    train, validation, test = [set(splits[name]) for name in ('train', 'validation', 'test')]
    assert not train & validation and not train & test and not validation & test
    assert len(train | validation | test) == 300
    assert len(train) == 180 and len(validation) == 60 and len(test) == 60
    assert set(bundle.model.feature_names_in_) == {
        'Type', 'Air temperature [K]', 'Process temperature [K]',
        'Rotational speed [rpm]', 'Torque [Nm]', 'Tool wear [min]'}
    report = bundle.report
    assert sum(map(sum, report['test']['confusion_matrix'])) == 60
    assert report['threshold_selected_on'] == 'validation'
    assert report['remaining_useful_life'] is None
    assert 'most_frequent_baseline' in report


def test_input_rejects_leaked_target_missing_feature_and_nonfinite(dataset):
    a = api()
    record = pd.read_csv(dataset).iloc[0][a.FEATURES].to_dict()
    for changes in ({'Machine failure': 1}, {'Torque [Nm]': float('nan')}, {'Type': 'X'}):
        with pytest.raises(ValueError):
            a.Observation.model_validate(record | changes)
    del record['Tool wear [min]']
    with pytest.raises(ValueError):
        a.Observation.model_validate(record)


def test_dataset_flow_creates_only_idempotent_review_orders(dataset, tmp_path):
    a = api()
    bundle = a.fit_baseline(dataset)
    frame = pd.read_csv(dataset)
    row = frame[(frame['Machine failure'] == 1) & (frame['Tool wear [min]'] > 0)].iloc[0]
    raw = row[a.FEATURES].to_dict()
    first = a.run_record(bundle, raw, str(row['UDI']), tmp_path / 'orders.sqlite')
    second = a.run_record(bundle, raw, str(row['UDI']), tmp_path / 'orders.sqlite')
    assert first.predicted_failure is True
    assert first.order.status == 'review_required'
    assert first.order.order_id == second.order.order_id
    assert first.order.proposal.part_id is None
    assert first.remaining_life is None


def test_invalid_model_evidence_falls_back_without_altering_prediction(dataset, tmp_path):
    a = api()
    bundle = a.fit_baseline(dataset)
    row = pd.read_csv(dataset).iloc[5]
    class Hostile:
        def generate(self, payload):
            return json.dumps({'evidence_ids': ['invented-part']})
    result = a.run_record(bundle, row[a.FEATURES].to_dict(), '6', tmp_path / 'orders.sqlite', provider=Hostile())
    assert result.explanation_mode == 'fallback'
    assert result.predicted_failure is True
    assert 'invented-part' not in result.model_dump_json()


def test_out_of_training_range_abstains(dataset, tmp_path):
    a = api()
    bundle = a.fit_baseline(dataset)
    raw = pd.read_csv(dataset).iloc[5][a.FEATURES].to_dict()
    raw['Torque [Nm]'] = 10000
    result = a.run_record(bundle, raw, 'outside', tmp_path / 'orders.sqlite')
    assert result.predicted_failure is None and result.score is None
    assert result.order.status == 'review_required'


def test_bad_dataset_labels_rejected(dataset):
    a = api()
    frame = pd.read_csv(dataset)
    frame.loc[0, 'Machine failure'] = 2
    frame.to_csv(dataset, index=False)
    with pytest.raises(ValueError):
        a.fit_baseline(dataset)


def test_metrics_count_false_alarms_and_missed_failures():
    a = api()
    import numpy as np
    result = a.metrics(np.array([0, 0, 1, 1]), np.array([0.1, 0.8, 0.9, 0.2]), 0.5)
    assert result['confusion_matrix'] == [[1, 1], [1, 1]]
    assert result['precision'] == 0.5 and result['recall'] == 0.5


def test_downloader_never_overwrites_existing_data(tmp_path):
    a = api()
    path = tmp_path / 'existing.csv'
    path.write_text('keep teammate work')
    with pytest.raises(FileExistsError):
        a.download_dataset(path)
    assert path.read_text() == 'keep teammate work'


def test_dataset_dashboard_replays_without_aws(dataset, tmp_path, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    page = Path('pages/1_AI4I_Baseline.py')
    assert page.exists(), 'Dataset dashboard is not implemented'
    monkeypatch.setenv('AI4I_CSV', str(dataset))
    monkeypatch.setenv('DEMO_MODE', 'offline')
    monkeypatch.setenv('DEMO_LEDGER_PATH', str(tmp_path / 'dashboard.sqlite'))
    monkeypatch.setenv('NOTIFY_OUTBOX_PATH', str(tmp_path / 'notify.sqlite'))
    app = AppTest.from_file(str(page), default_timeout=30).run()
    assert not app.exception
    # Title names the console; explorer is not shown before an assessment.
    assert any('Machine maintenance console' in t.value for t in app.title)
    assert len(app.get('iframe')) == 0
    # Assess the default record and policy.
    app.button[0].click().run()
    assert not app.exception
    # The decision metric is populated and the explorer iframe is rendered.
    assert any(getattr(m, 'label', '') == 'Decision' for m in app.metric)
    iframes = app.get('iframe')
    assert iframes and 'GLOBAL ASSESSMENT' in iframes[0].proto.srcdoc


def test_dataset_dashboard_hides_stale_result_when_record_changes(dataset, tmp_path, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('AI4I_CSV', str(dataset))
    monkeypatch.setenv('DEMO_MODE', 'offline')
    monkeypatch.setenv('DEMO_LEDGER_PATH', str(tmp_path / 'stale.sqlite'))
    monkeypatch.setenv('NOTIFY_OUTBOX_PATH', str(tmp_path / 'notify.sqlite'))
    app = AppTest.from_file('pages/1_AI4I_Baseline.py', default_timeout=30).run()
    app.button[0].click().run()
    assert len(app.get('iframe')) == 1
    # Changing the record selector must retract the previous result immediately.
    record_select = app.selectbox[1]
    record_select.select(record_select.options[1]).run()
    assert not app.exception
    assert len(app.get('iframe')) == 0
    assert any('Selection changed' in w.value for w in app.warning)


def test_dataset_dashboard_hides_stale_result_when_policy_changes(dataset, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('AI4I_CSV', str(dataset))
    monkeypatch.setenv('DEMO_MODE', 'offline')
    monkeypatch.setenv('DEMO_LEDGER_PATH', str(tmp_path / 'stalep.sqlite'))
    monkeypatch.setenv('NOTIFY_OUTBOX_PATH', str(tmp_path / 'notify.sqlite'))
    app = AppTest.from_file('pages/1_AI4I_Baseline.py', default_timeout=30).run()
    app.button[0].click().run()
    assert len(app.get('iframe')) == 1
    # Switching the operating policy must retract the previous result too.
    app.selectbox[0].select('gradient_boosting').run()
    assert not app.exception
    assert len(app.get('iframe')) == 0
    assert any('Selection changed' in w.value for w in app.warning)
