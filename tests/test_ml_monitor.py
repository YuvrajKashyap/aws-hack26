"""Monitor/alerts/diagnosis integration safety for the isolated ml experiment.

These tests use an injected predictor, so they never load model.joblib and never
require lightgbm/xgboost. They assert the stable per-unit/episode alert id,
rejection of bad readings before state mutation, simulated-by-default notification,
and the offline-by-default diagnosis agent.
"""
import socket

import pytest


def _pred(risk):
    def predictor(sm):
        return {"risk": risk, "threshold": 0.05, "risk_kind": "calibrated_model",
                "evidence": ["vib", "lube", "temp"], "rul_hours": 20,
                "rul_range_hours": [18, 24],
                "rul_method": "wear-threshold projection (heuristic, not validated RUL)",
                "failure_mode": "bearing_wear", "model_risk": risk,
                "heuristic_risk": risk, "confidence": risk}
    return predictor


def _reading(unit, i, **over):
    r = {"ts": f"2026-10-23T14:0{i}:00Z", "unit_id": unit, "rpm": 1450, "torque": 38,
         "vibration": 2.0, "temp_c": 45, "power_kw": 7, "lube_ppm": 12, "tool_wear_min": 60}
    r.update(over)
    return r


def test_monitor_injectable_predictor_needs_no_model():
    from ml.monitor import Monitor
    mon = Monitor(predictor=_pred(0.01))
    out = mon.process(_reading("CRAC-1", 0))
    assert out["state"] == "normal"
    assert out["prediction"]["risk"] == 0.01


def test_stable_alert_id_survives_interleaved_second_unit_alert():
    from ml.monitor import Monitor
    mon = Monitor(predictor=_pred(0.9))        # every reading is above threshold
    # CRAC-3 reaches alert first (needs ALERT_TICKS consecutive).
    mon.process(_reading("CRAC-3", 0))
    a1 = mon.process(_reading("CRAC-3", 1))
    assert a1["state"] == "alert"
    aid = a1["alert_id"]
    assert aid and aid.startswith("ALT-CRAC-3-")
    # Now CRAC-1 opens its own alert (interleaved). CRAC-3's id must not change.
    mon.process(_reading("CRAC-1", 2))
    b = mon.process(_reading("CRAC-1", 3))
    assert b["state"] == "alert"
    assert b["alert_id"].startswith("ALT-CRAC-1-")
    assert b["alert_id"] != aid
    # CRAC-3 keeps its original identity on its next tick.
    a2 = mon.process(_reading("CRAC-3", 4))
    assert a2["alert_id"] == aid


@pytest.mark.parametrize("bad", [
    {"vibration": float("nan")},
    {"temp_c": float("inf")},
    {"lube_ppm": "oops"},
])
def test_bad_reading_rejected_before_state_mutation(bad):
    from ml.monitor import Monitor
    mon = Monitor(predictor=_pred(0.01))
    mon.process(_reading("CRAC-1", 0))           # establish healthy EWMA
    ewma_before = dict(mon.ewma["CRAC-1"])
    with pytest.raises(ValueError):
        mon.process(_reading("CRAC-1", 1, **bad))
    # Smoothing state unchanged by the rejected reading.
    assert mon.ewma["CRAC-1"] == ewma_before


def test_missing_channel_rejected():
    from ml.monitor import Monitor
    mon = Monitor(predictor=_pred(0.01))
    r = _reading("CRAC-1", 0)
    del r["vibration"]
    with pytest.raises(ValueError):
        mon.process(r)


def test_alerts_notify_is_simulated_and_no_network(monkeypatch, tmp_path):
    def forbidden(*a, **k):
        raise AssertionError("no network allowed in simulated notify")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    # A topic env must NOT cause a real send without explicit opt-in.
    monkeypatch.setenv("NOTIFY_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:ops")
    from ml.monitor import Monitor
    from ml.alerts import AlertManager
    mon = Monitor(predictor=_pred(0.9))
    am = AlertManager(to=["ops@example.com"], outbox=str(tmp_path / "outbox.jsonl"))
    out = None
    for i in range(3):
        out = am.process(mon.process(_reading("CRAC-3", i, vibration=4.6, temp_c=52,
                                              lube_ppm=30, tool_wear_min=180)))
    assert out["severity"] == "high"
    assert out["email"]["mode"] == "simulated"
    assert out["email"]["delivered"] is False


def test_notifier_cannot_go_live_without_publisher(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTIFY_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:ops")
    from ml.alerts import Notifier
    # allow_live True but no publisher -> still simulated (no bypass).
    n = Notifier(to=["x@e.com"], outbox=str(tmp_path / "o.jsonl"), allow_live=True, publisher=None)
    rec = n.send(("CRAC-3", 1, "high"), "subj", "body", "2026-10-23T14:00:00Z")
    assert rec["mode"] == "simulated" and rec["delivered"] is False


def test_diagnosis_defaults_offline_without_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("no network allowed in offline diagnosis")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.delenv("DIAG_MODE", raising=False)
    from ml.diagnosis import Diagnosis
    out = {"unit_id": "CRAC-3", "alert_id": "ALT-CRAC-3-001", "severity": "high",
           "tick": {"ts": "2026-10-23T14:00:00Z"},
           "recommendation": {"summary": "Inspect", "why": ["x"], "part_id": "BRG-6205"},
           "prediction": _pred(0.9)(None)}
    res = Diagnosis(use_cache=False).run(out, [out["tick"]])
    d = res["diagnosis"]
    assert d["source"] == "fallback"
    assert "offline" in d["fallback_reason"]
    # Numbers come from predict, not an LLM.
    assert d["numbers"]["source"].startswith("predict.py")


def test_diagnosis_cache_key_depends_on_inputs_and_manual_version():
    from ml.diagnosis import Diagnosis, MANUAL_VERSION
    base = {"unit_id": "CRAC-3", "alert_id": "ALT-CRAC-3-001", "severity": "high",
            "tick": {"ts": "t"}, "prediction": _pred(0.9)(None)}
    k1 = Diagnosis._cache_key(base, [{"risk": 0.9}])
    changed = dict(base, prediction=_pred(0.5)(None))
    k2 = Diagnosis._cache_key(changed, [{"risk": 0.9}])
    assert k1 != k2                               # different numbers -> different key
    assert MANUAL_VERSION in k1                   # manual version folded in
    k3 = Diagnosis._cache_key(base, [{"risk": 0.1}])
    assert k1 != k3                               # different history -> different key
