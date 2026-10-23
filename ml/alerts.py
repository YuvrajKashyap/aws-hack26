"""Alert severity, replacement recommendation, and customer notification.

Wraps the Monitor output. Deterministic Python, no LLM.

    from monitor import Monitor
    from alerts import AlertManager
    mon, am = Monitor(), AlertManager(to=["ops@yourcompany.com"])
    out = am.process(mon.process(reading))
    out["severity"]         # None | "low" | "medium" | "high"
    out["recommendation"]   # action + component + part + "why" bullets (None if no alert)
    out["events"]           # monitor events + severity escalations + notifier event

Severity (edit the constants to tune):
    watch state                          -> low
    alert, risk < 40% and life > 48 h    -> low
    alert, risk >= 40% or life <= 48 h   -> medium
    alert, risk >= 70% or life <= 24 h   -> high   (customer is emailed once per alert)
Severity only goes up within one open alert, and resets when the unit returns to normal.

Email: by default SIMULATED. The email is written to outbox.jsonl and shown in the UI.
To really send, create an SNS topic with an email subscription (the recipient must click the
confirmation link) and set NOTIFY_SNS_TOPIC_ARN. The workshop account may block this, so keep
the simulated mode as the demo default and say so.
"""
import json
import os

SEV_ORDER = {"low": 1, "medium": 2, "high": 3}
HIGH_RISK, MED_RISK = 0.70, 0.40
HIGH_RUL_H, MED_RUL_H = 24.0, 48.0

# SIMULATED parts catalog. Part ids and lead times are placeholders, not real data.
# Align with teammate's parts.json when it exists.
CATALOG = {
    "bearing_wear": ("Fan motor bearing assembly", "BRG-6205", 3),
    "heat_dissipation_fault": ("Heat-exchange coil service kit", "COIL-KIT-01", 5),
    "motor_power_fault": ("Fan motor drive (VFD)", "VFD-22K", 7),
    "overstrain_fault": ("Fan belt and impeller kit", "FAN-KIT-02", 2),
    "default": ("General inspection", None, 0),
}
ACTIONS = {
    "low": ("inspect_and_lubricate", "Inspect and lubricate; keep the part on order as a precaution"),
    "medium": ("replace_component_next_window", "Replace the component at the next planned window"),
    "high": ("replace_component_now", "Replace the component now, in an emergency window"),
}


def classify(pred, state):
    """Return (severity, reason). severity is None when the unit is normal."""
    if state == "normal":
        return None, ""
    risk, rul = pred["risk"], pred["rul_hours"]
    if state == "watch":
        return "low", "drift detected, still below the alert threshold"
    if risk >= HIGH_RISK:
        return "high", f"risk {risk:.0%} is at or above {HIGH_RISK:.0%}"
    if rul <= HIGH_RUL_H:
        return "high", f"estimated life {rul:.0f} h is at or below {HIGH_RUL_H:.0f} h"
    if risk >= MED_RISK:
        return "medium", f"risk {risk:.0%} is at or above {MED_RISK:.0%}"
    if rul <= MED_RUL_H:
        return "medium", f"estimated life {rul:.0f} h is at or below {MED_RUL_H:.0f} h"
    return "low", f"alert raised, but risk {risk:.0%} and life {rul:.0f} h are not yet urgent"


def recommend(pred, sev, reason):
    comp, part, lead_days = CATALOG.get(pred["failure_mode"], CATALOG["default"])
    action, summary = ACTIONS[sev]
    lo, hi = pred["rul_range_hours"]
    why = list(pred["evidence"][:3])
    why.append(f"estimated remaining life about {lo:.0f}-{hi:.0f} h "
               "(wear-threshold projection, heuristic, not a validated RUL)")
    if part:
        if lead_days * 24 > hi:
            why.append(f"part lead time {lead_days} days (placeholder) is longer than the estimated "
                       "life, so expedite shipping or use a spare")
        else:
            why.append(f"part lead time {lead_days} days (placeholder) fits inside the estimated life")
    why.append(f"severity {sev.upper()}: {reason}")
    if sev == "high":
        why.append("move workloads off the affected racks before the swap")
    return {
        "action": action, "summary": summary, "component": comp, "part_id": part,
        "lead_time_days": lead_days, "why": why, "catalog": "simulated",
        "scope_note": ("Whole-unit replacement is not recommended from this data: we have no asset "
                       "age, repair history or unit price. A component swap is the targeted fix."),
    }


def approval_link(alert_id, unit):
    """Set APPROVAL_URL_TEMPLATE, e.g. https://host/approve/{alert_id}. Else tell the reader where to go."""
    tpl = os.getenv("APPROVAL_URL_TEMPLATE")
    if tpl:
        return tpl.format(alert_id=alert_id, unit_id=unit)
    return f"open the maintenance dashboard and review alert {alert_id}"


def build_email(unit, sev, pred, rec, alert_id, ts, approval=None):
    mode = pred["failure_mode"].replace("_", " ")
    lo, hi = pred["rul_range_hours"]
    subject = f"[{sev.upper()}] {unit} {mode}: act within about {lo:.0f} h"
    lines = [
        f"Alert {alert_id} for {unit} at {ts}",
        f"Severity: {sev.upper()}   Risk: {pred['risk']:.0%}   "
        f"Estimated remaining life: {lo:.0f}-{hi:.0f} h (heuristic)",
        f"Likely cause: {mode}",
        "",
        f"Recommended action: {rec['summary']}",
        f"Component: {rec['component']}" + (f" ({rec['part_id']})" if rec["part_id"] else ""),
        "",
        "Why:",
        *[f"  - {w}" for w in rec["why"]],
        "",
        "Nothing has been ordered or scheduled. An operator must approve the plan first:",
        f"  {approval or approval_link(alert_id, unit)}",
        "",
        "This is a prototype using simulated sensor data and a simulated parts catalog.",
    ]
    return subject, "\n".join(lines)


class Notifier:
    def __init__(self, to=("ops@example.com",), outbox="outbox.jsonl"):
        self.to, self.outbox = list(to), outbox
        self.topic = os.getenv("NOTIFY_SNS_TOPIC_ARN")
        self.sent = set()

    def send(self, key, subject, body, ts):
        if key in self.sent:
            return None
        self.sent.add(key)
        mode, err = "simulated", None
        if self.topic:
            try:
                import boto3
                boto3.client("sns", region_name="us-east-1").publish(
                    TopicArn=self.topic, Subject=subject[:100], Message=body)
                mode = "sns"
            except Exception as e:           # never let a notification failure break the pipeline
                mode, err = "sns_failed_logged_only", str(e)[:120]
        rec = {"ts": ts, "to": self.to, "subject": subject, "body": body, "mode": mode, "error": err}
        with open(self.outbox, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec


class AlertManager:
    def __init__(self, to=("ops@example.com",), outbox="outbox.jsonl"):
        self.notifier = Notifier(to, outbox)
        self.sev, self.episode = {}, {}

    def process(self, out):
        u, pred, state = out["unit_id"], out["prediction"], out["state"]
        ts = out["tick"]["ts"]
        sev, reason = classify(pred, state)
        old = self.sev.get(u)

        if sev is None:                                   # back to normal: reset
            self.sev[u] = None
            out.update(severity=None, severity_reason="", recommendation=None)
            return out
        if old is None:
            self.episode[u] = self.episode.get(u, 0) + 1
        if old is not None and SEV_ORDER[sev] < SEV_ORDER[old]:
            sev = old                                      # severity never drops inside one episode
            reason = out.get("severity_reason") or reason
        self.sev[u] = sev
        rec = recommend(pred, sev, reason)
        out.update(severity=sev, severity_reason=reason, recommendation=rec)
        out["tick"]["severity"] = sev

        for e in out["events"]:                            # tag existing monitor events
            e["data"]["severity"] = sev
        if old is not None and SEV_ORDER[sev] > SEV_ORDER[old]:
            out["events"].append({
                "ts": ts, "agent": "monitor",
                "status": "alert" if sev == "high" else "warning",
                "message": f"{u}: severity raised to {sev.upper()} ({reason})",
                "data": {"unit_id": u, "from_severity": old, "severity": sev, "risk": pred["risk"]}})

        if sev == "high":
            subject, body = build_email(u, sev, pred, rec, out.get("alert_id") or "ALT-?", ts)
            sent = self.notifier.send((u, self.episode[u], "high"), subject, body, ts)
            if sent:
                if sent["mode"] == "sns":
                    msg = "High-severity alert published to the SNS email topic (real email to subscribers)"
                elif sent["mode"] == "simulated":
                    msg = f"High-severity alert emailed to {', '.join(sent['to'])} (simulated, no real email sent)"
                else:
                    msg = f"High-severity email NOT sent ({sent['error']}); logged only"
                out["events"].append({
                    "ts": ts, "agent": "notifier", "status": "alert", "message": msg,
                    "data": {"unit_id": u, "subject": sent["subject"], "mode": sent["mode"]}})
                out["email"] = sent
        return out


if __name__ == "__main__":
    from monitor import Monitor
    from simulator import Simulator
    sim, mon, am = Simulator(), Monitor(), AlertManager(outbox="outbox_demo.jsonl")
    open("outbox_demo.jsonl", "w").close()
    last = None
    for k in range(48):
        if k == 12:
            sim.inject("CRAC-3")
        for r in sim.step():
            out = am.process(mon.process(r))
            if r["unit_id"] != "CRAC-3":
                assert out["severity"] is None, f"false alarm on {r['unit_id']}"
                continue
            for e in out["events"]:
                print(f"tick {k:>2} [{e['status']:<7}] {e['agent']:<8} {e['message']}")
            last = out
    print("\n--- recommendation at the end ---")
    print(json.dumps(last["recommendation"], indent=2))
    mails = [json.loads(x) for x in open("outbox_demo.jsonl")]
    print(f"\nemails written: {len(mails)}")
    print("\n" + mails[0]["subject"] + "\n\n" + mails[0]["body"])