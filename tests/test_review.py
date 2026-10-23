import pytest
from src.review import ReviewStore


def test_review_persists_and_rejects_concurrent_overwrite(tmp_path):
    store = ReviewStore(tmp_path/'review.sqlite')
    row = store.save('SIM-WO-123', 'Acknowledged', 'Demo review accepted')
    assert ReviewStore(store.path).get('SIM-WO-123') == row
    with pytest.raises(ValueError, match='another session'):
        store.save('SIM-WO-123', 'Review completed', 'Stale update')
    updated = store.save('SIM-WO-123', 'Review completed', 'Synthetic inspection complete', 1)
    assert updated['version'] == 2


def test_review_requires_note_and_simulated_order(tmp_path):
    store = ReviewStore(tmp_path/'review.sqlite')
    for order, state, note in [('REAL-1','Acknowledged','x'), ('SIM-WO-1','Unknown','x'), ('SIM-WO-1','Review completed',' ')]:
        with pytest.raises(ValueError):
            store.save(order, state, note)
