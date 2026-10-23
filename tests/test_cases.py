"""Record search and failure-case catalog stay honest about labels and side effects."""
import pandas as pd
import pytest

from src.cases import FAILURE_MODES, case_catalog, describe_record, preview_outcomes, search_records


def frame():
    rows = []
    for i in range(1, 41):
        mode = {1: 'TWF', 2: 'HDF', 3: 'PWF', 4: 'OSF', 5: 'RNF'}.get(i)
        row = {'UDI': i, 'Product ID': f'L{1000 + i}', 'Type': 'LMH'[i % 3],
               'Air temperature [K]': 298.0 + i / 10, 'Process temperature [K]': 308.0 + i / 10,
               'Rotational speed [rpm]': 1400 + i, 'Torque [Nm]': 40.0 + (50 if mode else 0), 'Tool wear [min]': i * 5,
               'Machine failure': int(mode is not None)}
        for code in FAILURE_MODES:
            row[code] = int(code == mode)
        rows.append(row)
    return pd.DataFrame(rows).set_index('UDI')


def test_search_by_mode_code_name_type_udi_and_health():
    f = frame()
    assert search_records(f, 'HDF').index.tolist() == [2]
    assert search_records(f, 'heat').index.tolist() == [2]
    assert search_records(f, 'failure').index.tolist() == [1, 2, 3, 4, 5]
    assert len(search_records(f, 'healthy')) == 35
    assert search_records(f, 'L1003').index.tolist() == [3]
    assert search_records(f, '1').index.tolist() == [1] + list(range(10, 20))
    assert set(search_records(f, 'M failure')['Type']) <= {'M'}
    assert search_records(f, '').equals(f)
    assert search_records(f, 'zzz').empty


def test_catalog_has_one_case_per_mode_plus_healthy_and_abstain():
    f = frame()
    bounds = {'Torque [Nm]': [0, 80]}
    cases = case_catalog(f, bounds)
    ids = [c.case_id for c in cases]
    assert ids == ['twf', 'hdf', 'pwf', 'osf', 'rnf', 'healthy', 'abstain']
    by_id = {c.case_id: c for c in cases}
    assert by_id['hdf'].record_id == 2 and by_id['hdf'].mode == 'HDF'
    assert by_id['healthy'].record_id == 6
    assert 'Torque [Nm]' in by_id['abstain'].dataset_says
    assert all('Dataset rule' in c.dataset_says for c in cases if c.mode)
    assert case_catalog(f, None)[-1].case_id == 'healthy'


def test_describe_record_lists_modes_without_claiming_diagnosis():
    f = frame()
    assert describe_record(f.loc[2]) == '2 · L1002 · type H · failure HDF'
    assert describe_record(f.loc[6]).endswith('no failure')


class StubPolicy:
    threshold = 0.5

    def score_row(self, values):
        return 0.9 if values['Torque [Nm]'] > 60 else 0.1


def test_preview_outcomes_scores_without_ledger_and_abstains_out_of_range():
    f = frame()
    bounds = {'Torque [Nm]': [0, 80]}
    features = ['Type', 'Air temperature [K]', 'Process temperature [K]', 'Rotational speed [rpm]', 'Torque [Nm]', 'Tool wear [min]']
    table = preview_outcomes(case_catalog(f, bounds), f, StubPolicy(), bounds, features)
    assert list(table.columns) == ['Case', 'Record', 'Dataset label', 'Score', 'Threshold', 'Decision', 'Simulated order']
    decisions = dict(zip(table['Case'], table['Decision']))
    assert decisions['Below-threshold comparison'] == 'Below threshold'
    assert decisions['Out-of-range abstention'] == 'Abstained'
    assert table.loc[table['Decision'] == 'Abstained', 'Score'].isna().all()
    assert (table.loc[table['Decision'] == 'Below threshold', 'Simulated order'] == 'none').all()
