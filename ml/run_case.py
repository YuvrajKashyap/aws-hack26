"""End-to-end agentic demo: live stream -> alert -> agent crew plans -> human approves -> repair -> verify.

    python3 run_case.py                    # random scenario, asks you to approve in the terminal
    python3 run_case.py --auto-approve     # no prompt
    python3 run_case.py --seed 7           # repeatable scenario (cached runs replay for free)
    DIAG_MODE=offline python3 run_case.py  # no Bedrock calls, deterministic fallbacks
Set NOTIFY_SNS_TOPIC_ARN to email the crew's message for real. All data is simulated.
"""
import argparse
import random
import time

from agents import Crew
from alerts import AlertManager, Notifier
from monitor import Monitor
from simulator import Simulator

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=float, default=0.5)
ap.add_argument("--ticks", type=int, default=90)
ap.add_argument("--seed", type=int, default=None)
ap.add_argument("--auto-approve", action="store_true")
a = ap.parse_args()


def show(e):
    print(f"{e['ts']}  [{e['status']:<7}] {e['agent']:<11} {e['message']}", flush=True)


sim = Simulator(seed=a.seed)
rnd = random.Random(sim.seed)
unit, inject_at = rnd.choice(sim.units), rnd.randint(8, 20)
print(f"scenario seed={sim.seed}: fault on {unit} at tick {inject_at} (simulated)\n")

mon, am = Monitor(), AlertManager(outbox="outbox_live.jsonl")
am.notifier.send = lambda *x, **k: None          # in crew mode the Comms agent writes the email
mailer = Notifier(outbox="outbox_crew.jsonl")
crew = Crew(on_event=show)
fleet, history, case, repaired_at = {}, [], None, None

for k in range(a.ticks):
    if k == inject_at:
        sim.inject(unit)
    for r in sim.step():
        o = am.process(mon.process(r))
        fleet[r["unit_id"]] = {"state": o["state"], "risk": o["prediction"]["risk"],
                               "vibration": round(o["smoothed"]["vibration"], 2)}
        if r["unit_id"] != unit:
            continue
        history.append(o["tick"])
        for e in o["events"]:
            show(e)

        if case is None and o.get("severity") in ("medium", "high"):
            case = crew.open_case(o, history, fleet)
            print("\n================ PLAN FOR APPROVAL ================")
            print(case["plan"]["headline"])
            for i, s in enumerate(case["plan"]["steps"], 1):
                print(f"  {i}. {s}")
            print(f"\nEMAIL: {case['email']['subject']}\n{case['email']['body']}")
            print("===================================================\n")
            sent = mailer.send(case["case_id"], case["email"]["subject"], case["email"]["body"], r["ts"])
            show({"ts": r["ts"], "agent": "notifier", "status": "done",
                  "message": f"{unit}: crew email {'published to SNS' if sent['mode'] == 'sns' else sent['mode']}"})
            yes = a.auto_approve or input("Approve this plan? [y/N] ").strip().lower() == "y"
            if yes:
                crew.approve(case, sim, now=r["ts"])
                repaired_at = k
            else:
                crew.reject(case, reason="operator declined in terminal")

        if repaired_at is not None and case["status"] == "verifying" and (k - repaired_at) >= 4 \
                and (k - repaired_at) % 3 == 1:
            crew.verify(case, o, history)
            if case["status"] in ("closed", "reopened"):
                print(f"\ncase {case['case_id']} -> {case['status'].upper()}")
                raise SystemExit
    time.sleep(a.interval)
print(f"\nstream ended, case status: {case['status'] if case else 'no case opened'}")
