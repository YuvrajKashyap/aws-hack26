"""Monitor/alerts/diagnosis integration safety for the isolated ml experiment.

These tests use an injected predictor, so they never load model.joblib and never
require lightgbm/xgboost. They assert the stable per-unit/episode alert id,
rejection of bad readings before state mutation, simulated-by-default notification,
and the offline-by-default diagnosis agent.
"""
import json
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


def test_diagnosis_cache_key_depends_on_full_context(monkeypatch):
    from ml import diagnosis as D
    from ml.diagnosis import Diagnosis
    base = {"unit_id": "CRAC-3", "alert_id": "ALT-CRAC-3-001", "severity": "high",
            "tick": {"ts": "t"}, "prediction": _pred(0.9)(None),
            "recommendation": {"summary": "x", "part_id": "BRG-6205"}}
    k1 = Diagnosis._cache_key(base, [{"risk": 0.9, "smoothed": {"vibration": 4.6}}])
    # Different prediction numbers -> different key.
    assert k1 != Diagnosis._cache_key(dict(base, prediction=_pred(0.5)(None)),
                                      [{"risk": 0.9, "smoothed": {"vibration": 4.6}}])
    # Different history sample (including the smoothed channels the model can read) -> different key.
    assert k1 != Diagnosis._cache_key(base, [{"risk": 0.9, "smoothed": {"vibration": 9.9}}])
    # Manual/parts reference version is folded in: changing it changes the key.
    monkeypatch.setattr(D, "MANUAL_VERSION", "CHANGED")
    assert k1 != Diagnosis._cache_key(base, [{"risk": 0.9, "smoothed": {"vibration": 4.6}}])


def test_repeated_high_ticks_dedupe_to_one_notification_and_publish(tmp_path):
    """Two high ticks with different timestamp and score, plus a reopened Notifier on
    the same outbox, must produce one notification and exactly one live publish."""
    from ml.alerts import build_email, recommend, classify, Notifier

    class CountingPub:
        n = 0
        def publish(self, s, b):
            CountingPub.n += 1
            return f"m{CountingPub.n}"
    pub = CountingPub()
    db = str(tmp_path / "outbox.jsonl")   # mapped to .sqlite internally

    def high_payload(ts, risk):
        pred = _pred(risk)(None)
        sev, reason = "high", f"risk {risk:.0%}"
        rec = recommend(pred, sev, reason)
        return build_email("CRAC-3", sev, pred, rec, "ALT-CRAC-3-001", ts)

    key = ("CRAC-3", 1, "high")
    s1, b1 = high_payload("2026-10-23T14:00:00Z", 0.70)
    r1 = Notifier(to=["ops@example.com"], outbox=db, allow_live=True, publisher=pub).send(key, s1, b1, "t1")
    assert r1["status"] == "accepted"
    # Reopen the Notifier (fresh instance, same DB); new tick, changed ts and score.
    s2, b2 = high_payload("2026-10-23T14:10:00Z", 0.83)
    assert s2 != s1 or b2 != b1
    r2 = Notifier(to=["ops@example.com"], outbox=db, allow_live=True, publisher=pub).send(key, s2, b2, "t2")
    assert r2["notification_id"] == r1["notification_id"]
    assert CountingPub.n == 1                 # exactly one publish despite changed content


def test_diagnosis_does_not_render_fabricated_model_numbers_or_actions(monkeypatch):
    """A hostile live model returns invented numbers, parts, prose and actions. The
    rendered diagnosis must contain NONE of it: numbers come from predict.py, actions
    from the deterministic recommendation/template, and evidence/citations are validated."""
    monkeypatch.setenv("DIAG_MODE", "live")
    from ml.diagnosis import Diagnosis

    pred = _pred(0.77)(None)
    out = {"unit_id": "CRAC-3", "alert_id": "ALT-CRAC-3-001", "severity": "high",
           "tick": {"ts": "2026-10-23T14:00:00Z"},
           "recommendation": {"summary": "Replace the component at the next planned window",
                              "why": ["x"], "part_id": "BRG-6205"},
           "prediction": pred}

    # Scripted fake Bedrock client: first search the manual (to seed a valid citation),
    # then submit a hostile diagnosis stuffed with fabricated content.
    class HostileClient:
        step = 0
        def converse(self, **kwargs):
            HostileClient.step += 1
            if HostileClient.step == 1:
                return {"output": {"message": {"content": [{"toolUse": {
                    "name": "search_manual", "toolUseId": "t1",
                    "input": {"query": "bearing wear severity"}}}]}}}
            return {"output": {"message": {"content": [{"toolUse": {
                "name": "submit_diagnosis", "toolUseId": "t2", "input": {
                    "root_cause": "CATASTROPHIC MELTDOWN imminent in 2 minutes",
                    "confidence": "high",
                    "summary": "Risk is 99.9% and remaining life is 0 hours. Order 5 units now.",
                    "evidence": [],
                    "citations": ["SIM-MAN-4.2"],
                    "next_steps": ["Dispatch emergency crew and auto-order parts immediately"]}}}]}}}

    res = Diagnosis(client=HostileClient(), use_cache=False).run(out, [out["tick"]])
    d = res["diagnosis"]
    blob = json.dumps(d).lower()
    # None of the fabricated prose/numbers/actions/parts survive rendering.
    for fab in ("catastrophic", "meltdown", "2 minutes", "99.9", "order 5", "fabricated",
                "invented evidence", "fake-part-123", "emergency crew", "auto-order"):
        assert fab not in blob, f"fabricated content leaked: {fab}"
    # Numbers come from predict.py; evidence is the predictor's; part from recommendation.
    assert d["numbers"]["risk"] == pred["risk"]
    assert d["numbers"]["source"].startswith("predict.py")
    assert set(d["evidence"]) <= set(pred["evidence"])
    assert d["part"] is None or d["part"]["part_id"] == "BRG-6205"
    # The model's validated confidence enum and valid citation are allowed through.
    assert d["confidence"] == "high"
    assert d["citations"] and d["citations"][0]["id"] == "SIM-MAN-4.2"
