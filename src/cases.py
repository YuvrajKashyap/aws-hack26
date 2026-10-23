"""Record search and a demo catalog of AI4I failure cases.

The catalog groups held-out records by the dataset's documented failure-mode
columns (TWF, HDF, PWF, OSF, RNF) so a presenter can pick a case, read what the
published dataset says caused it, and see what the console will do. The mode
columns are used only for selection and display; they never enter the classifier.
"""
from dataclasses import dataclass, field

import pandas as pd

MODE_COLUMNS = ['TWF', 'HDF', 'PWF', 'OSF', 'RNF']

# Published AI4I 2020 generation rules (Matzka, 2020). These describe how the
# synthetic dataset labelled each row, not a diagnosis of any real machine.
FAILURE_MODES = {
    'TWF': {
        'title': 'Tool wear failure',
        'rule': 'Dataset rule: the tool fails or is replaced at a randomly chosen wear time between 200 and 240 minutes.',
        'watch': 'Tool wear near or above 200 min in the Tool head zone.',
    },
    'HDF': {
        'title': 'Heat dissipation failure',
        'rule': 'Dataset rule: air-to-process temperature difference below 8.6 K while rotational speed is below 1380 rpm.',
        'watch': 'Small temperature gap in the Process chamber zone and low rpm in the Drive zone.',
    },
    'PWF': {
        'title': 'Power failure',
        'rule': 'Dataset rule: torque x rotational speed (in rad/s) below 3500 W or above 9000 W.',
        'watch': 'Unusual torque and rpm combination in the Drive zone.',
    },
    'OSF': {
        'title': 'Overstrain failure',
        'rule': 'Dataset rule: tool wear x torque above 11000 minNm for type L, 12000 for M, 13000 for H.',
        'watch': 'High torque together with high tool wear; threshold depends on product type.',
    },
    'RNF': {
        'title': 'Random failure',
        'rule': 'Dataset rule: 0.1 percent of rows fail regardless of process values.',
        'watch': 'Readings look ordinary. A low score here is expected and shows the limits of the classifier.',
    },
}


@dataclass
class DemoCase:
    case_id: str
    record_id: int
    title: str
    mode: str | None
    dataset_says: str
    expected: str
    watch_for: str
    tags: list[str] = field(default_factory=list)


def record_modes(row) -> list[str]:
    return [code for code in MODE_COLUMNS if code in row.index and int(row[code]) == 1]


def describe_record(row) -> str:
    """One-line label for a record picker."""
    modes = record_modes(row)
    label = 'failure ' + '+'.join(modes) if modes else ('failure' if int(row.get('Machine failure', 0)) == 1 else 'no failure')
    product = row.get('Product ID', '')
    return f"{row.name} · {product} · type {row['Type']} · {label}"


def search_records(heldout: pd.DataFrame, query: str) -> pd.DataFrame:
    """Filter held-out records by UDI, product id, type, failure-mode code or name.

    Tokens are ANDed. Examples: "HDF", "heat", "L 2016", "failure", "healthy", "M50".
    """
    if heldout.empty:
        return heldout
    tokens = [t for t in str(query).lower().split() if t]
    if not tokens:
        return heldout
    mask = pd.Series(True, index=heldout.index)
    failure = heldout['Machine failure'].astype(int) == 1 if 'Machine failure' in heldout else pd.Series(False, index=heldout.index)
    for token in tokens:
        upper = token.upper()
        if token in ('healthy', 'normal', 'ok', 'nofailure'):
            hit = ~failure
        elif token in ('failure', 'failed', 'fail', 'flag', 'flagged'):
            hit = failure
        elif upper in MODE_COLUMNS and upper in heldout:
            hit = heldout[upper].astype(int) == 1
        elif token.isdigit():
            hit = heldout.index.astype(str).str.startswith(token)
        elif len(token) == 1 and upper in ('L', 'M', 'H'):
            hit = heldout['Type'] == upper
        else:
            hit = pd.Series(False, index=heldout.index)
            for code, info in FAILURE_MODES.items():
                if code in heldout and token in info['title'].lower():
                    hit |= heldout[code].astype(int) == 1
            if 'Product ID' in heldout:
                hit |= heldout['Product ID'].astype(str).str.lower().str.contains(token, regex=False)
        mask &= hit
    return heldout[mask]


def _outside(row, bounds) -> list[str]:
    return [name for name, (low, high) in (bounds or {}).items()
            if name in row.index and not low <= float(row[name]) <= high]


def case_catalog(heldout: pd.DataFrame, bounds: dict | None = None) -> list[DemoCase]:
    """Pick one representative held-out record per documented failure mode plus
    a healthy comparison and, when one exists, an out-of-range abstention case."""
    cases: list[DemoCase] = []
    failure = heldout['Machine failure'].astype(int) == 1
    for code, info in FAILURE_MODES.items():
        if code not in heldout:
            continue
        candidates = heldout[failure & (heldout[code].astype(int) == 1)]
        if candidates.empty:
            continue
        # Prefer single-mode rows so the story is clean; deterministic lowest UDI.
        single = candidates[candidates[MODE_COLUMNS].astype(int).sum(axis=1) == 1]
        row = (single if not single.empty else candidates).sort_index().iloc[0]
        cases.append(DemoCase(
            case_id=code.lower(), record_id=int(row.name), title=info['title'], mode=code,
            dataset_says=info['rule'],
            expected='Dataset label is failure. A review-flagged decision creates a simulated technician-review order; '
                     'a below-threshold decision is a documented miss, not a safe machine.',
            watch_for=info['watch'], tags=['failure', code]))
    healthy = heldout[~failure]
    if not healthy.empty:
        row = healthy.sort_index().iloc[0]
        cases.append(DemoCase(
            case_id='healthy', record_id=int(row.name), title='Below-threshold comparison', mode=None,
            dataset_says='Dataset label is no failure. Readings sit inside the ordinary operating envelope.',
            expected='Expected decision: below threshold. No order is created. This is not a declaration that equipment is safe.',
            watch_for='All three zones read ordinary. Compare the score with a flagged case.', tags=['healthy']))
    if bounds:
        outside = heldout[[bool(_outside(r, bounds)) for _, r in heldout.iterrows()]]
        if not outside.empty:
            row = outside.sort_index().iloc[0]
            cases.append(DemoCase(
                case_id='abstain', record_id=int(row.name), title='Out-of-range abstention', mode=None,
                dataset_says='One or more inputs fall outside the training range: ' + ', '.join(_outside(row, bounds)) + '.',
                expected='Expected decision: abstained. No score is produced and the proposal still requests review, '
                         'because silence outside the training range is unsafe.',
                watch_for='The quality flag names the out-of-range input; no classifier score is shown.', tags=['abstain']))
    return cases


def preview_outcomes(cases: list[DemoCase], heldout: pd.DataFrame, policy, bounds: dict, features: list[str]) -> pd.DataFrame:
    """Score every catalog case with the active policy, without touching the ledger."""
    rows = []
    for case in cases:
        row = heldout.loc[case.record_id]
        values = row[features].to_dict()
        flags = _outside(row, bounds)
        score = None if flags else policy.score_row(values)
        decision = 'Abstained' if score is None else ('Review flagged' if score >= policy.threshold else 'Below threshold')
        rows.append({
            'Case': case.title, 'Record': case.record_id, 'Dataset label': 'failure' if int(row['Machine failure']) == 1 else 'no failure',
            'Score': None if score is None else round(float(score), 4), 'Threshold': policy.threshold,
            'Decision': decision,
            'Simulated order': 'review order' if decision != 'Below threshold' else 'none',
        })
    return pd.DataFrame(rows)
