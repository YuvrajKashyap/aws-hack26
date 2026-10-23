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
