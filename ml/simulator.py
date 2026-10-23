"""CRAC telemetry simulator. Healthy values match the constants in predict.py.

    from simulator import Simulator
    sim = Simulator()                 # CRAC-1..CRAC-4, all healthy
    readings = sim.step()             # list of sensor-reading dicts (shared contract)
    sim.inject("CRAC-3")              # start a bearing fault on one unit
    sim.reset()

    python3 simulator.py              # demo: 12 healthy ticks, inject, 30 ticks, prints risk

One tick = 10 simulated minutes. ALL channels are simulated (AI4I has no vibration or
lube data). Say so in the pitch.
"""
import datetime as dt
import os

import numpy as np

# healthy means: keep in sync with predict.py
RPM, TORQUE, VIB, TEMP_C, LUBE = 1450.0, 38.0, 2.0, 45.0, 12.0
TICK_MIN = 10
WEAR_PER_TICK = 0.5          # 3 wear-min per simulated hour
FAULT_TICKS = 24             # ticks for severity to ramp 0 -> 1 (4 simulated hours)


class Simulator:
    def __init__(self, units=("CRAC-1", "CRAC-2", "CRAC-3", "CRAC-4"), seed=None,
                 start_wear=60.0, start=None):
        """No seed (default): every run is different, and timestamps start at the current time.
        seed=7 or SIM_SEED=7: identical every run (use this on stage so cached replays match)."""
        env = os.getenv("SIM_SEED")
        if seed is None and env:
            seed = int(env)
        fixed = seed is not None
        if seed is None:
            seed = int(np.random.SeedSequence().entropy % (2 ** 31))
        self.units = list(units)
        self.seed, self.start_wear = seed, start_wear
        if start is None:
            if fixed:
                start = dt.datetime(2026, 10, 23, 14, 0, tzinfo=dt.timezone.utc)
            else:
                now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
                start = now - dt.timedelta(minutes=now.minute % TICK_MIN)
        self.start = start
        self.reset()

    def reset(self):
        self.rng = np.random.default_rng(self.seed)
        self.t = 0
        self.wear = {u: self.start_wear for u in self.units}
        self.fault_tick = {}          # unit_id -> tick when fault was injected

    def inject(self, unit_id, fault="bearing"):
        if unit_id not in self.units:
            raise ValueError(f"unknown unit {unit_id}")
        self.fault_tick[unit_id] = self.t

    def severity(self, unit_id):
        if unit_id not in self.fault_tick:
            return 0.0
        return float(min(1.0, (self.t - self.fault_tick[unit_id]) / FAULT_TICKS))

    def _reading(self, u):
        r, s = self.rng, self.severity(u)
        rpm = r.normal(RPM, 12) - 60 * s
        torque = r.normal(TORQUE, 1.2) + 16 * s
        vib = r.normal(VIB, 0.08) * (1 + 1.6 * s) + 0.5 * s * abs(r.normal(0, 1))
        temp = r.normal(TEMP_C, 0.4) + 8 * s
        lube = r.normal(LUBE, 0.6) * (1 + 1.8 * s)
        self.wear[u] += WEAR_PER_TICK + 3.0 * s * 0.5     # faster ageing during fault
        power = torque * rpm * 2 * np.pi / 60 / 1000 / 0.8
        ts = self.start + dt.timedelta(minutes=TICK_MIN * self.t)
        return {"ts": ts.isoformat().replace("+00:00", "Z"), "unit_id": u,
                "rpm": round(float(rpm), 1), "torque": round(float(torque), 2),
                "vibration": round(float(vib), 2), "temp_c": round(float(temp), 2),
                "power_kw": round(float(power), 2), "lube_ppm": round(float(lube), 1),
                "tool_wear_min": round(self.wear[u], 1)}

    def step(self):
        out = [self._reading(u) for u in self.units]
        self.t += 1
        return out


if __name__ == "__main__":
    from predict import predict
    sim = Simulator()
    print(f"{'tick':>4} {'sev':>4} {'vib':>5} {'lube':>5} {'risk':>5} {'rul_h':>6}  mode / driver")
    for k in range(42):
        if k == 12:
            sim.inject("CRAC-3")
            print("---- fault injected on CRAC-3 ----")
        reading = next(r for r in sim.step() if r["unit_id"] == "CRAC-3")
        p = predict(reading)
        print(f"{k:>4} {sim.severity('CRAC-3'):>4.2f} {reading['vibration']:>5.2f} "
              f"{reading['lube_ppm']:>5.1f} {p['risk']:>5.2f} {p['rul_hours']:>6.1f}  "
              f"{p['failure_mode']} / {p['risk_kind']}")