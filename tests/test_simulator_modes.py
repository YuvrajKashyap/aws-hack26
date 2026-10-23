from ml.simulator import Simulator


def test_default_replay_remains_reproducible():
    assert Simulator().step() == Simulator().step()


def test_opt_in_random_mode_accepts_reproducible_environment(monkeypatch):
    monkeypatch.setenv('SIM_SEED', '19')
    assert Simulator(seed=None).step() == Simulator(seed=19).step()
