"""Live-style run: a fresh random scenario every time, one tick per --interval seconds.

    python3 live.py                      # random unit and fault time, 2 s per tick, 60 ticks
    python3 live.py --interval 0.2       # faster
    python3 live.py --seed 7             # repeat the same scenario (stage rehearsal)
    LIVE_DIAG=1 python3 live.py          # also run the Bedrock diagnosis agent at the first HIGH
    DIAG_MODE=offline LIVE_DIAG=1 ...    # same, with the no-network fallback
All readings are simulated.
"""
import argparse
import os
import random
import time

from alerts import AlertManager
from cost import estimate
from monitor import Monitor
from simulator import Simulator

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=float, default=2.0)
ap.add_argument("--ticks", type=int, default=60)
ap.add_argument("--seed", type=int, default=None)
a = ap.parse_args()

sim = Simulator(seed=a.seed)
rnd = random.Random(sim.seed)
unit, inject_at = rnd.choice(sim.units), rnd.randint(8, 20)
print(f"scenario seed={sim.seed}: fault on {unit} at tick {inject_at} (simulated)\n")

mon, am = Monitor(), AlertManager(outbox="outbox_live.jsonl")
dg = None
if os.getenv("LIVE_DIAG"):
    from diagnosis import Diagnosis
    dg = Diagnosis()
history, costed, diagnosed = [], False, False
for k in range(a.ticks):
    if k == inject_at:
        sim.inject(unit)
    for r in sim.step():
        o = am.process(mon.process(r))
        if r["unit_id"] != unit:
            continue
        history.append(o["tick"])
        for e in o["events"]:
            print(f"{r['ts']}  [{e['status']:<7}] {e['agent']:<8} {e['message']}")
        if o.get("severity") in ("medium", "high") and not costed:
            costed = True
            for e in estimate(o)["events"]:
                print(f"{r['ts']}  [{e['status']:<7}] {e['agent']:<8} {e['message']}")
        if dg and o.get("severity") == "high" and not diagnosed:
            diagnosed = True
            for e in dg.run(o, history)["events"]:
                print(f"{r['ts']}  [{e['status']:<7}] {e['agent']:<8} {e['message']}")
    time.sleep(a.interval)
