"""Monitor agent: smooths sensor readings, scores risk, raises alerts with hysteresis.

Deterministic Python, no LLM (an honest "rules + model" agent, not an LLM agent).

    from monitor import Monitor
    mon = Monitor()
    out = mon.process(reading)     # call once per reading, per unit
    out["state"]                   # "normal" | "watch" | "alert"
    out["events"]                  # list of agent-event dicts (empty unless state changed)
    out["tick"]                    # dict for the dashboard timeline

States (threshold comes from train.py, chosen on validation data):
    watch : risk >= WATCH_FRAC x threshold
    alert : risk >= threshold for ALERT_TICKS consecutive ticks
    back to normal only after risk stays under the watch level for CLEAR_TICKS ticks.
"""
from predict import LUBE_BASE, VIB_BASE, predict

ALPHA = 0.35         # EWMA weight on the newest reading (lower = smoother, slower)
WATCH_FRAC = 0.3
ALERT_TICKS = 2
CLEAR_TICKS = 3
SMOOTHED = ["vibration", "lube_ppm", "temp_c", "torque", "rpm"]
BAND = {"vibration": (VIB_BASE, VIB_BASE * 1.3), "lube_ppm": (LUBE_BASE, LUBE_BASE * 1.5)}


class Monitor:
    def __init__(self):
        self.ewma = {}      # unit_id -> {channel: value}
        self.state = {}     # unit_id -> "normal"|"watch"|"alert"
        self.above = {}     # unit_id -> consecutive ticks at/above threshold
        self.calm = {}      # unit_id -> consecutive ticks under watch level
        self.alert_no = 0

    def _smooth(self, u, r):
        prev = self.ewma.get(u)
        cur = {c: float(r[c]) for c in SMOOTHED}
        if prev:
            cur = {c: ALPHA * cur[c] + (1 - ALPHA) * prev[c] for c in SMOOTHED}
        self.ewma[u] = cur
        return dict(r, **cur)

    def process(self, reading):
        u = reading["unit_id"]
        sm = self._smooth(u, reading)
        pred = predict(sm)
        thr = pred["threshold"]
        watch_lvl = WATCH_FRAC * thr
        old = self.state.get(u, "normal")

        self.above[u] = self.above.get(u, 0) + 1 if pred["risk"] >= thr else 0
        self.calm[u] = self.calm.get(u, 0) + 1 if pred["risk"] < watch_lvl else 0

        new = old
        if self.above[u] >= ALERT_TICKS:
            new = "alert"
        elif old == "alert":
            new = "normal" if self.calm[u] >= CLEAR_TICKS else "alert"
        elif pred["risk"] >= watch_lvl:
            new = "watch"
        else:
            new = "normal"
        self.state[u] = new

        events = []
        if new != old:
            if new == "alert":
                self.alert_no += 1
            events.append(self._event(reading, u, old, new, pred))

        return {
            "unit_id": u, "state": new, "prediction": pred, "smoothed": sm,
            "events": events, "alert_id": f"ALT-{self.alert_no:03d}" if new == "alert" else None,
            "tick": {
                "ts": reading["ts"], "unit_id": u, "risk": pred["risk"],
                "threshold": thr, "watch_level": round(watch_lvl, 3), "state": new,
                "raw": {c: reading[c] for c in ("vibration", "lube_ppm", "temp_c")},
                "smoothed": {c: round(sm[c], 2) for c in ("vibration", "lube_ppm", "temp_c")},
                "bands": {c: {"baseline": b, "limit": lim} for c, (b, lim) in BAND.items()},
            },
        }

    def _event(self, r, u, old, new, pred):
        msg = {
            ("normal", "watch"): f"{u}: drift detected, watching ({pred['evidence'][0]})",
            ("watch", "alert"): f"{u}: risk {pred['risk']:.0%} over threshold {pred['threshold']:.0%}, alert raised",
            ("normal", "alert"): f"{u}: risk {pred['risk']:.0%} over threshold {pred['threshold']:.0%}, alert raised",
            ("alert", "normal"): f"{u}: readings back to normal, alert cleared",
            ("watch", "normal"): f"{u}: drift gone, back to normal",
            ("alert", "watch"): f"{u}: easing, still watching",
        }.get((old, new), f"{u}: {old} -> {new}")
        status = {"alert": "alert", "watch": "warning"}.get(new, "info")
        return {"ts": r["ts"], "agent": "monitor", "status": status, "message": msg,
                "data": {"unit_id": u, "from": old, "to": new, "risk": pred["risk"],
                         "risk_kind": pred["risk_kind"], "evidence": pred["evidence"]}}


if __name__ == "__main__":
    from simulator import Simulator
    sim, mon = Simulator(), Monitor()
    print(f"{'tick':>4} {'sev':>4} {'vib raw':>7} {'vib sm':>6} {'risk':>5}  state")
    for k in range(48):
        if k == 12:
            sim.inject("CRAC-3")
            print("---- fault injected on CRAC-3 ----")
        for r in sim.step():
            out = mon.process(r)
            if r["unit_id"] != "CRAC-3":
                assert out["state"] == "normal", f"false alarm on {r['unit_id']} tick {k}"
                continue
            t = out["tick"]
            print(f"{k:>4} {sim.severity('CRAC-3'):>4.2f} {t['raw']['vibration']:>7.2f} "
                  f"{t['smoothed']['vibration']:>6.2f} {t['risk']:>5.2f}  {out['state']}")
            for e in out["events"]:
                print(f"       EVENT [{e['status']}] {e['message']}")