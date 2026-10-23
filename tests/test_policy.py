"""Operating policies (RF, GB, hybrid) must select on validation only and never
confuse model identities across the ledger or cached explanations."""
import importlib.util
import json

import pandas as pd
import pytest

pytest.importorskip('sklearn', reason='Install requirements-ml.txt for policy tests')


def api():
    assert importlib.util.find_spec('src.policy') is not None, 'Policy layer not implemented'
    from src import policy
    return policy


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


def test_three_policies_are_available_and_named():
    p = api()
    assert set(p.POLICIES) == {'random_forest', 'gradient_boosting', 'hybrid_rf_gb'}


def test_hybrid_weight_grid_and_threshold_grid_are_fixed():
    p = api()
    assert p.HYBRID_WEIGHTS == [0.25, 0.5, 0.75]
    assert p.THRESHOLD_GRID == [i / 100 for i in range(5, 96, 5)]


def test_each_policy_fits_on_train_only_and_has_distinct_identity(dataset):
    p = api()
    from src.ai4i import fit_baseline
    baseline = fit_baseline(dataset)
    policies = {name: p.build_policy(name, dataset, baseline) for name in p.POLICIES}
    ids = [policy.model_id for policy in policies.values()]
    # Three usable policies with three distinct model identities.
    assert len(set(ids)) == 3
    # Identity must embed the recipe so caches/ledger cannot confuse models.
    assert policies['random_forest'].model_id.startswith('AI4I-RF')
    assert policies['gradient_boosting'].model_id.startswith('AI4I-GB')
    hybrid = policies['hybrid_rf_gb']
    assert hybrid.model_id.startswith('AI4I-HYB')
    # Hybrid identity encodes the chosen weight and threshold.
    assert str(hybrid.weight) in hybrid.recipe
    assert str(hybrid.threshold) in hybrid.recipe


def test_hybrid_weight_and_threshold_selected_on_validation_only(dataset):
    p = api()
    from src.ai4i import fit_baseline
    baseline = fit_baseline(dataset)
    hybrid = p.build_policy('hybrid_rf_gb', dataset, baseline)
    assert hybrid.weight in p.HYBRID_WEIGHTS
    assert hybrid.threshold in p.THRESHOLD_GRID
    assert hybrid.report['threshold_selected_on'] == 'validation'
    assert hybrid.report['weight_selected_on'] == 'validation'
    # Validation metrics are present and the chosen weight maximizes validation F2
    # over the fixed grid (no test influence on selection).
    best = max(hybrid.report['weight_search'],
               key=lambda e: (e['validation_f2'], e['validation_average_precision'], e['threshold']))
    assert best['weight'] == hybrid.weight
    assert best['threshold'] == hybrid.threshold


def test_hybrid_probability_is_weighted_average_of_bases(dataset):
    p = api()
    import numpy as np
    from src.ai4i import fit_baseline
    baseline = fit_baseline(dataset)
    hybrid = p.build_policy('hybrid_rf_gb', dataset, baseline)
    frame = pd.read_csv(dataset).set_index('UDI')
    from src.ai4i import FEATURES
    sample = frame[FEATURES].iloc[:5]
    rf = hybrid.base_scores('random_forest', sample)
    gb = hybrid.base_scores('gradient_boosting', sample)
    blended = hybrid.scores(sample)
    expected = hybrid.weight * rf + (1 - hybrid.weight) * gb
    assert np.allclose(blended, expected)


def test_policy_report_includes_rf_gb_hybrid_with_provenance(dataset):
    p = api()
    from src.ai4i import fit_baseline
    baseline = fit_baseline(dataset)
    report = p.compare_policies(dataset, baseline)
    assert set(report['policies']) == {'random_forest', 'gradient_boosting', 'hybrid_rf_gb'}
    for name, entry in report['policies'].items():
        assert 'validation' in entry and 'test' in entry
        assert 'confusion_matrix' in entry['test']
        assert entry['threshold'] in p.THRESHOLD_GRID
        assert entry['model_id']
    assert report['hybrid_weight'] in p.HYBRID_WEIGHTS
    assert report['dataset_sha256']
    assert report['seed'] == 42
    # Never claims the hybrid is best; it only records the measured selection.
    assert report['selection_scope']
    assert report['test_caveat']


def test_selectable_inference_each_policy_runs_a_record(dataset, tmp_path):
    p = api()
    from src.ai4i import FEATURES, fit_baseline, run_record
    baseline = fit_baseline(dataset)
    frame = pd.read_csv(dataset)
    row = frame[(frame['Machine failure'] == 1) & (frame['Tool wear [min]'] > 0)].iloc[0]
    raw = row[FEATURES].to_dict()
    results = {}
    for name in p.POLICIES:
        policy = p.build_policy(name, dataset, baseline)
        results[name] = run_record(baseline, raw, str(row['UDI']), tmp_path / 'orders.sqlite', policy=policy)
    # Each policy yields a result carrying its own identity.
    assert len({r.model_id for r in results.values()}) == 3
    for r in results.values():
        assert r.score is not None
        assert r.predicted_failure in (True, False)


def test_distinct_policies_do_not_share_a_ledger_order_key(dataset, tmp_path):
    p = api()
    from src.ai4i import FEATURES, fit_baseline, run_record
    baseline = fit_baseline(dataset)
    frame = pd.read_csv(dataset)
    row = frame[(frame['Machine failure'] == 1) & (frame['Tool wear [min]'] > 0)].iloc[0]
    raw = row[FEATURES].to_dict()
    db = tmp_path / 'orders.sqlite'
    orders = {}
    for name in p.POLICIES:
        policy = p.build_policy(name, dataset, baseline)
        r = run_record(baseline, raw, str(row['UDI']), db, policy=policy)
        if r.order is not None:
            orders[name] = r.order.order_id
    # Two policies both flagging the same record must not collide on one order key.
    assert len(set(orders.values())) == len(orders)


def test_same_policy_same_record_is_idempotent(dataset, tmp_path):
    p = api()
    from src.ai4i import FEATURES, fit_baseline, run_record
    baseline = fit_baseline(dataset)
    frame = pd.read_csv(dataset)
    row = frame[(frame['Machine failure'] == 1) & (frame['Tool wear [min]'] > 0)].iloc[0]
    raw = row[FEATURES].to_dict()
    db = tmp_path / 'orders.sqlite'
    policy = p.build_policy('hybrid_rf_gb', dataset, baseline)
    first = run_record(baseline, raw, str(row['UDI']), db, policy=policy)
    second = run_record(baseline, raw, str(row['UDI']), db, policy=policy)
    assert first.order.order_id == second.order.order_id


def test_invalid_model_evidence_falls_back_across_policies(dataset, tmp_path):
    p = api()
    from src.ai4i import FEATURES, fit_baseline, run_record
    baseline = fit_baseline(dataset)
    row = pd.read_csv(dataset).iloc[5]
    raw = row[FEATURES].to_dict()

    class Hostile:
        def generate(self, payload):
            return json.dumps({'evidence_ids': ['invented-part']})

    for name in p.POLICIES:
        policy = p.build_policy(name, dataset, baseline)
        r = run_record(baseline, raw, '6', tmp_path / f'{name}.sqlite', policy=policy, provider=Hostile())
        assert r.explanation_mode == 'fallback'
        assert 'invented-part' not in r.model_dump_json()
        assert r.remaining_life is None


def test_explorer_zone_observations_come_from_the_record():
    p = api()
    observation = {'Type': 'L', 'Air temperature [K]': 300.1, 'Process temperature [K]': 310.5,
                   'Rotational speed [rpm]': 1500, 'Torque [Nm]': 45.0, 'Tool wear [min]': 120}
    zones = p.explorer_zones(observation)
    names = {z['id'] for z in zones}
    assert names == {'drive', 'process_chamber', 'tool_head'}
    drive = next(z for z in zones if z['id'] == 'drive')
    # Drive zone reports the actual rotation/torque observation values.
    joined = ' '.join(drive['observations'])
    assert '1500' in joined and '45' in joined
    chamber = next(z for z in zones if z['id'] == 'process_chamber')
    assert '310.5' in ' '.join(chamber['observations'])
    head = next(z for z in zones if z['id'] == 'tool_head')
    assert '120' in ' '.join(head['observations'])
    # Zones must not fabricate component fault states.
    for z in zones:
        text = ' '.join(z['observations']).lower()
        assert 'failed' not in text and 'broken' not in text


def test_explorer_html_is_self_contained_and_shows_record_values():
    from src.explorer import render_machine_explorer
    observation = {'Type': 'M', 'Air temperature [K]': 301.2, 'Process temperature [K]': 311.7,
                   'Rotational speed [rpm]': 1420, 'Torque [Nm]': 52.3, 'Tool wear [min]': 199}
    from src.policy import explorer_zones
    zones = explorer_zones(observation)
    assessment = {'record_id': '123', 'model_id': 'AI4I-HYB-deadbeef', 'policy': 'hybrid_rf_gb',
                  'score': 0.73, 'threshold': 0.2, 'predicted_failure': True, 'explanation_mode': 'offline'}
    html = render_machine_explorer(zones, assessment)
    # No remote assets / build stack.
    assert 'http://' not in html and 'https://' not in html
    assert '<script' not in html.split('<body')[0] or 'src=' not in html
    # Actual record values and assessment identity are embedded, not a mockup.
    for token in ('1420', '52.3', '311.7', '199', '123', 'AI4I-HYB-deadbeef', 'hybrid_rf_gb'):
        assert token in html
    # Accessibility + reduced motion + illustrative labelling.
    assert 'prefers-reduced-motion' in html
    assert 'focus-visible' in html
    assert 'role="button"' in html and 'tabindex="0"' in html
    assert 'Illustrative' in html


def test_explorer_marks_abstention_without_inventing_fault():
    from src.explorer import render_machine_explorer
    from src.policy import explorer_zones
    observation = {'Type': 'L', 'Air temperature [K]': 300.0, 'Process temperature [K]': 310.0,
                   'Rotational speed [rpm]': 1500, 'Torque [Nm]': 40.0, 'Tool wear [min]': 10}
    assessment = {'record_id': '7', 'model_id': 'AI4I-RF-abc', 'policy': 'random_forest',
                  'score': None, 'threshold': 0.15, 'predicted_failure': None, 'explanation_mode': 'offline'}
    html = render_machine_explorer(zones=explorer_zones(observation), assessment=assessment)
    assert 'ABSTAINED' in html
    assert 'does not diagnose a specific component' in html


def test_explorer_draws_a_connected_silhouette_with_three_zones():
    from src.explorer import render_machine_explorer
    from src.policy import explorer_zones
    observation = {'Type': 'L', 'Air temperature [K]': 300.0, 'Process temperature [K]': 310.0,
                   'Rotational speed [rpm]': 1500, 'Torque [Nm]': 40.0, 'Tool wear [min]': 10}
    html = render_machine_explorer(zones=explorer_zones(observation),
        assessment={'record_id': '1', 'model_id': 'AI4I-RF-abc', 'policy': 'random_forest',
                    'score': 0.1, 'threshold': 0.15, 'predicted_failure': False, 'explanation_mode': 'offline'})
    # Connected silhouette: bed/rails and conduits linking the stations (not three isolated cards).
    assert 'class="frame"' in html and 'class="rail"' in html and 'class="conduit"' in html
    # The three clickable zones are retained.
    for zone_id in ('z-drive', 'z-process_chamber', 'z-tool_head'):
        assert zone_id in html
    assert html.count('class="zone"') == 3
    # Controls retained: zoom reset, keyboard handling, reduced motion.
    assert 'id="reset"' in html
    assert "e.key === 'Enter'" in html and "e.key === 'Escape'" in html
    assert 'prefers-reduced-motion' in html
