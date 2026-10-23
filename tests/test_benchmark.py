import pytest

pytest.importorskip('sklearn')


def test_selection_ignores_test_results():
    from src.benchmark import select_winner
    rows = [
        {'name': 'a', 'validation': {'f2': .8, 'average_precision': .7}, 'test': {'f2': 0}},
        {'name': 'b', 'validation': {'f2': .7, 'average_precision': .9}, 'test': {'f2': 1}},
    ]
    assert select_winner(rows) == 'a'
    rows[0]['test'], rows[1]['test'] = rows[1]['test'], rows[0]['test']
    assert select_winner(rows) == 'a'


def test_candidates_are_five_distinct_families_and_use_allowlist():
    from src.benchmark import candidates
    from src.ai4i import FEATURES
    models = candidates()
    assert len(models) == 5
    assert len({type(model.steps[-1][1]) for model in models.values()}) == 5
    for model in models.values():
        columns = model.steps[0][1].transformers
        assert set(columns[0][2] + columns[1][2]) == set(FEATURES)


def _small_dataset(tmp_path):
    import pandas as pd
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


def test_benchmark_report_includes_three_operating_policies(tmp_path):
    from src.benchmark import compare
    report = compare(_small_dataset(tmp_path))
    policies = report['operating_policies']['policies']
    assert set(policies) == {'random_forest', 'gradient_boosting', 'hybrid_rf_gb'}
    for entry in policies.values():
        assert 'validation' in entry and 'test' in entry
        assert entry['model_id']
    # Three distinct identities so the ledger/cache cannot confuse policies.
    assert len({entry['model_id'] for entry in policies.values()}) == 3
    assert report['operating_policies']['production_model_changed'] is False
