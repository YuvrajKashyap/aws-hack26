"""Maintenance crew: a Supervisor agent that runs specialist agents, all on Amazon Bedrock tool use.

    from agents import Crew
    crew = Crew()
    case = crew.open_case(out, history, fleet)   # agents plan the fix; stops at PENDING_APPROVAL
    crew.approve(case, sim)                      # human says yes -> PO logged, work booked, unit repaired
    crew.verify(case, out, history)              # Verifier agent confirms recovery, or reopens the case
    case["events"]                               # activity feed: every agent step and tool call

Agents (each is an LLM that chooses its own tools, then submits a structured answer):
    supervisor   decides which specialists to run and in what order, then submits the plan
    triage       is this a real unit fault or a site-wide / sensor issue? may RAISE severity, never lower it
    diagnosis    root cause with manual citations (diagnosis.py)
    impact       which racks lose cooling, how fast they overheat, which workloads to migrate
    procurement  use stock or draft a purchase order; picks supplier and shipping
    scheduler    picks the cost option and the crew shift
    comms        writes the customer email
    verifier     after the repair, decides: close, keep watching, or reopen

Guardrails (code, not the LLM):
    - every number (risk, life, costs, thermal minutes, arrival times) is computed by code
    - each answer is validated; one correction round, then a deterministic fallback marked "fallback"
    - the supervisor cannot run the scheduler before procurement when the part is out of stock,
      and cannot submit a plan that skips a required specialist
    - nothing is ordered, booked or repaired until a human approves
    - the verifier cannot close a case while the unit is still alerting
ALL site data (racks, suppliers, crew shifts, prices) is SIMULATED.
"""
import json
import os
import re
import time

from cost import estimate
from diagnosis import MODEL_ID, PARTS_STOCK, Diagnosis, _make_client, _throttle

SEV = {"low": 1, "medium": 2, "high": 3}

# ---------------- simulated site data ----------------
MAX_INLET_C = 32.0           # rack inlet limit (ASHRAE A1 allowable upper bound)
NEIGHBOR_SPARE_KW = 30.0     # cooling the other units can pick up if one goes offline
RISE_C_PER_MIN_PER_KW = 0.05
RACKS = {u: [{"rack_id": f"R{i * 3 + j + 1:02d}", "tier": t, "load_kw": kw, "inlet_c": inlet}
             for j, (t, kw, inlet) in enumerate([("critical", 18.0, 24.0), ("standard", 14.0, 23.5),
                                                  ("batch", 10.0, 23.0)])]
         for i, u in enumerate(["CRAC-1", "CRAC-2", "CRAC-3", "CRAC-4"])}
SUPPLIERS = {
    "BRG-6205": [
        {"supplier_id": "SUP-A", "name": "Sim Bearings Co", "price_usd": 1800, "lead_days": 3,
         "expedite_days": 1, "expedite_fee_usd": 450},
        {"supplier_id": "SUP-B", "name": "Sim Parts Depot", "price_usd": 2100, "lead_days": 2,
         "expedite_days": 1, "expedite_fee_usd": 200}],
}
for _pid, _p in PARTS_STOCK.items():
    SUPPLIERS.setdefault(_pid, [{"supplier_id": "SUP-A", "name": "Sim Bearings Co", "price_usd": 900,
                                 "lead_days": _p["lead_time_days"], "expedite_days": _p["expedite_days"],
                                 "expedite_fee_usd": _p["expedite_fee_usd"]}])
SHIFTS = [{"shift_id": "S1", "starts_in_hours": 6, "crew": "night crew"},
          {"shift_id": "S2", "starts_in_hours": 14, "crew": "day crew"},
          {"shift_id": "S3", "starts_in_hours": 26, "crew": "night crew"},
          {"shift_id": "S4", "starts_in_hours": 38, "crew": "day crew"},
          {"shift_id": "S5", "starts_in_hours": 74, "crew": "planned maintenance window"}]


def thermal(unit, migrate=()):
    """What happens to the unit's racks if it goes offline, after moving `migrate` racks away."""
    racks = RACKS[unit]
    staying = [r for r in racks if r["rack_id"] not in migrate]
    load = sum(r["load_kw"] for r in staying)
    uncovered = max(0.0, load - NEIGHBOR_SPARE_KW)
    rate = uncovered * RISE_C_PER_MIN_PER_KW
    hottest = max((r["inlet_c"] for r in staying), default=0)
    minutes = round((MAX_INLET_C - hottest) / rate) if rate > 0 else None
    return {"load_kw_staying": load, "neighbor_spare_kw": NEIGHBOR_SPARE_KW, "uncovered_kw": uncovered,
            "minutes_to_thermal_limit": minutes, "safe_to_take_offline": minutes is None,
            "migration_minutes": 15 * len(migrate), "max_inlet_c": MAX_INLET_C}


def _nums(text):
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


class Crew:
    def __init__(self, client=None, cache_path="crew_cache.json", use_cache=True, max_steps=5, on_event=None):
        self.client, self.cache_path, self.use_cache, self.max_steps = client, cache_path, use_cache, max_steps
        self.on_event = on_event          # optional callback(event) for a live feed
        self.cache = {}
        if use_cache and os.path.exists(cache_path):
            try:
                self.cache = json.load(open(cache_path))
            except Exception:
                self.cache = {}
        self.diag = Diagnosis(client=client, use_cache=use_cache)
        self.offline = os.getenv("DIAG_MODE") == "offline"

    # ================= generic tool-use loop =================
    def _converse(self, system, messages, tools):
        if self.client is None:
            self.client = _make_client()
            self.diag._client = self.client
        _throttle()
        return self.client.converse(modelId=MODEL_ID, system=[{"text": system}], messages=messages,
                                    toolConfig={"tools": tools}, inferenceConfig={"maxTokens": 1500})

    def _run(self, case, agent, system, prompt, tools, submit, validate, max_steps=None):
        """tools: {name: (description, properties, required, fn(args))}. submit: (description, schema).
        Returns (answer or None, reason)."""
        if self.offline:
            return None, "offline mode"
        specs = [{"toolSpec": {"name": n, "description": d, "inputSchema": {"json": dict(
            {"type": "object", "properties": p}, **({"required": r} if r else {}))}}}
                 for n, (d, p, r, _) in tools.items()]
        specs.append({"toolSpec": {"name": "submit", "description": submit[0],
                                   "inputSchema": {"json": submit[1]}}})
        system = (system + "\nRules: use the tools to get facts; never invent numbers; all data is "
                  "simulated; you recommend, a human approves. Call submit exactly once at the end.")
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        corrected = nudged = False
        try:
            for _ in range(max_steps or self.max_steps):
                msg = self._converse(system, messages, specs)["output"]["message"]
                messages.append(msg)
                uses = [b["toolUse"] for b in msg["content"] if "toolUse" in b]
                if not uses:
                    if nudged:
                        return None, "never submitted"
                    nudged = True
                    messages.append({"role": "user", "content": [{"text": "Call submit now."}]})
                    continue
                results = []
                for tu in uses:
                    name, args, tid = tu["name"], tu.get("input") or {}, tu["toolUseId"]
                    if name == "submit":
                        problems = validate(args)
                        if not problems:
                            return args, None
                        if corrected:
                            return None, "invalid after correction: " + "; ".join(problems)[:120]
                        corrected = True
                        self._ev(case, agent, "warning", f"answer rejected by guardrail: {'; '.join(problems)[:120]}")
                        results.append({"toolResult": {"toolUseId": tid, "status": "error", "content": [
                            {"text": "Rejected: " + "; ".join(problems) + ". Fix and submit again."}]}})
                        continue
                    fn = tools.get(name, (None, None, None, None))[3]
                    try:
                        res, status = (fn(args), "success") if fn else ({"error": f"unknown tool {name}"}, "error")
                    except Exception as e:
                        res, status = {"error": str(e)[:120]}, "error"
                    self._ev(case, agent, "running", f"called {name}({json.dumps(args)[:60] if args else ''})")
                    results.append({"toolResult": {"toolUseId": tid, "status": status,
                                                   "content": [{"text": json.dumps(res, default=str)}]}})
                messages.append({"role": "user", "content": results})
            return None, f"no answer within {max_steps or self.max_steps} turns"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"

    def _ev(self, case, agent, status, msg, data=None):
        e = {"ts": case.get("now", case["ts"]), "agent": agent, "status": status,
             "message": f"{case['unit_id']}: {msg}", "data": data or {}}
        case["events"].append(e)
        if self.on_event:
            self.on_event(e)

    def _finish(self, case, agent, ans, reason, fallback, assemble):
        src = "llm"
        if ans is None:
            ans, src = fallback(), "fallback"
            self._ev(case, agent, "warning", f"using fallback ({reason})")
        result = dict(assemble(ans), source=src)
        case["results"][agent] = result
        self._ev(case, agent, "done", result.get("headline", "done"), result)
        return result

    # ================= specialists =================
    def triage(self, case):
        out, rule = case["out"], case["out"].get("severity") or "low"
        tools = {
            "get_prediction": ("Risk, life range, failure mode and evidence for the unit.", {}, [],
                               lambda a: {k: out["prediction"][k] for k in ("risk", "risk_kind", "threshold",
                                          "failure_mode", "rul_range_hours", "evidence")}),
            "get_sensor_history": ("Recent smoothed readings for the unit.", {}, [],
                                   lambda a: [{"ts": t["ts"], **t["smoothed"], "risk": t["risk"]}
                                              for t in case["history"][-8:]]),
            "get_fleet_status": ("Latest state and risk of every cooling unit on site.", {}, [],
                                 lambda a: case["fleet"]),
        }
        schema = {"type": "object", "properties": {
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            "is_unit_fault": {"type": "boolean", "description": "false if it looks site-wide or a sensor issue"},
            "rationale": {"type": "string"}}, "required": ["severity", "is_unit_fault", "rationale"]}
        val = lambda a: ([] if a.get("severity") in SEV else ["severity must be low/medium/high"]) + \
                        ([] if isinstance(a.get("is_unit_fault"), bool) else ["is_unit_fault must be true/false"])
        ans, why = self._run(case, "triage",
                             "You are the Triage agent for datacenter cooling units. Decide whether the alert "
                             "is a real fault on this unit or a site-wide/sensor problem, and how urgent it is.",
                             f"Alert {case['alert_id']} on {case['unit_id']}, rule severity {rule}.",
                             tools, ("Submit the triage decision.", schema), val)

        def assemble(a):
            sev = a["severity"] if SEV[a["severity"]] >= SEV[rule] else rule   # may raise, never lower
            return {"severity": sev, "rule_severity": rule, "llm_severity": a["severity"],
                    "is_unit_fault": a["is_unit_fault"], "rationale": a["rationale"],
                    "headline": f"severity {sev.upper()}" + ("" if a["is_unit_fault"] else ", possibly site-wide")
                                + f": {a['rationale'][:90]}"}
        return self._finish(case, "triage", ans, why, lambda: {
            "severity": rule, "is_unit_fault": True, "rationale": "rule-based severity"}, assemble)

    def diagnosis(self, case):
        res = self.diag.run(case["out"], case["history"])
        case["events"].extend(res["events"])
        for e in res["events"]:
            if self.on_event:
                self.on_event(e)
        d = res["diagnosis"]
        case["results"]["diagnosis"] = dict(d, headline=d["root_cause"])
        return case["results"]["diagnosis"]

    def impact(self, case):
        u = case["unit_id"]
        ids = [r["rack_id"] for r in RACKS[u]]
        tools = {
            "get_rack_impact": ("Racks this unit cools (tier, load, inlet temp) and what happens if it "
                                "goes offline with no migration.", {}, [],
                                lambda a: {"racks": RACKS[u], "if_offline": thermal(u)}),
            "simulate_migration": ("Thermal result if the listed racks' workloads are moved elsewhere first.",
                                   {"racks": {"type": "array", "items": {"type": "string"}}}, ["racks"],
                                   lambda a: thermal(u, [r for r in a.get("racks", []) if r in ids])),
        }
        schema = {"type": "object", "properties": {
            "migrate_racks": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"}}, "required": ["migrate_racks", "rationale"]}

        def val(a):
            bad = [r for r in a.get("migrate_racks", []) if r not in ids]
            p = [f"unknown racks {bad}"] if bad else []
            if not p and not thermal(u, a["migrate_racks"])["safe_to_take_offline"]:
                p.append("with that migration the racks still overheat while the unit is offline; "
                         "use simulate_migration to find a safe set")
            return p
        ans, why = self._run(case, "impact",
                             "You are the Impact agent. Plan how to take the cooling unit offline for repair "
                             "without overheating its racks, moving as few critical workloads as possible.",
                             f"{u} needs a repair. Which workloads must move first?",
                             tools, ("Submit the migration plan.", schema), val)

        def fallback():
            order = sorted(RACKS[u], key=lambda r: {"batch": 0, "standard": 1, "critical": 2}[r["tier"]])
            mig = []
            for r in order:
                if thermal(u, mig)["safe_to_take_offline"]:
                    break
                mig.append(r["rack_id"])
            return {"migrate_racks": mig, "rationale": "move lowest-priority workloads first until safe"}

        def assemble(a):
            t0, t1 = thermal(u), thermal(u, a["migrate_racks"])
            return {"migrate_racks": a["migrate_racks"], "rationale": a["rationale"],
                    "minutes_to_limit_without_migration": t0["minutes_to_thermal_limit"], "after": t1,
                    "headline": f"migrate {', '.join(a['migrate_racks']) or 'nothing'} "
                                f"({t1['migration_minutes']} min); without it racks hit "
                                f"{MAX_INLET_C:.0f} C in {t0['minutes_to_thermal_limit']} min"}
        return self._finish(case, "impact", ans, why, fallback, assemble)

    def _part(self, case):
        d = case["results"].get("diagnosis") or {}
        return ((d.get("part") or {}).get("part_id")
                or (case["out"].get("recommendation") or {}).get("part_id"))

    def procurement(self, case):
        pid, (lo, hi) = self._part(case), case["out"]["prediction"]["rul_range_hours"]
        stock = PARTS_STOCK.get(pid, {})
        tools = {
            "check_parts_stock": ("Stock level of the part.", {}, [], lambda a: dict(stock, part_id=pid)),
            "list_suppliers": ("Suppliers, prices, lead and expedite times for the part.", {}, [],
                               lambda a: SUPPLIERS.get(pid, [])),
            "get_deadline": ("Estimated remaining life of the unit in hours (heuristic range).", {}, [],
                             lambda a: {"rul_range_hours": [lo, hi]}),
        }
        schema = {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["use_stock", "draft_po"]},
            "supplier_id": {"type": "string"}, "shipping": {"type": "string", "enum": ["standard", "expedite"]},
            "qty": {"type": "integer"}, "rationale": {"type": "string"}},
            "required": ["action", "rationale"]}
        sup_ids = {s["supplier_id"] for s in SUPPLIERS.get(pid, [])}

        def val(a):
            if a.get("action") == "use_stock":
                return [] if stock.get("in_stock", 0) > 0 else ["part is out of stock, draft a PO"]
            p = [] if a.get("supplier_id") in sup_ids else [f"supplier must be one of {sorted(sup_ids)}"]
            if a.get("shipping") not in ("standard", "expedite"):
                p.append("shipping must be standard or expedite")
            if not 1 <= int(a.get("qty") or 0) <= 4:
                p.append("qty must be 1-4")
            return p
        ans, why = self._run(case, "procurement",
                             "You are the Procurement agent. Get the replacement part in time at sensible cost. "
                             "You only DRAFT purchase orders; a human approves them.",
                             f"Part {pid} is needed for {case['unit_id']}.",
                             tools, ("Submit the procurement decision.", schema), val)

        def fallback():
            if stock.get("in_stock", 0) > 0:
                return {"action": "use_stock", "rationale": "part in stock"}
            s = min(SUPPLIERS[pid], key=lambda s: s["price_usd"])
            ship = "expedite" if s["lead_days"] * 24 > lo else "standard"
            return {"action": "draft_po", "supplier_id": s["supplier_id"], "shipping": ship, "qty": 1,
                    "rationale": "cheapest supplier; expedite if standard shipping lands after the life estimate"}

        def assemble(a):
            if a["action"] == "use_stock":
                return {"action": "use_stock", "part_id": pid, "arrival_hours": 0, "total_usd": 0,
                        "rationale": a["rationale"], "headline": f"use {pid} from stock"}
            s = next(x for x in SUPPLIERS[pid] if x["supplier_id"] == a["supplier_id"])
            exp = a["shipping"] == "expedite"
            qty = int(a.get("qty") or 1)
            arrival = (s["expedite_days"] if exp else s["lead_days"]) * 24
            total = s["price_usd"] * qty + (s["expedite_fee_usd"] if exp else 0)
            return {"action": "draft_po", "part_id": pid, "supplier": s["name"], "supplier_id": s["supplier_id"],
                    "shipping": a["shipping"], "qty": qty, "arrival_hours": arrival, "total_usd": total,
                    "rationale": a["rationale"], "status": "DRAFT, not placed",
                    "headline": f"draft PO: {qty} x {pid} from {s['name']}, {a['shipping']}, "
                                f"arrives in ~{arrival} h, ${total:,} (not placed)"}
        return self._finish(case, "procurement", ans, why, fallback, assemble)

    def scheduler(self, case):
        card = estimate(case["out"])
        case["results"]["cost"] = card
        proc = case["results"].get("procurement") or {}
        arrival = proc.get("arrival_hours", 0)
        lo, hi = case["out"]["prediction"]["rul_range_hours"]
        tools = {
            "get_cost_options": ("Expected-cost options (placeholder dollar inputs).", {}, [],
                                 lambda a: {"options": card["options"], "cheapest": card["recommended"]}),
            "get_part_arrival": ("Hours until the part is on site.", {}, [], lambda a: {"arrival_hours": arrival}),
            "get_crew_shifts": ("Available crew shifts, hours from now.", {}, [], lambda a: SHIFTS),
            "get_deadline": ("Estimated remaining life (heuristic range, hours).", {}, [],
                             lambda a: {"rul_range_hours": [lo, hi]}),
        }
        schema = {"type": "object", "properties": {
            "option_id": {"type": "string", "enum": [o["id"] for o in card["options"]]},
            "shift_id": {"type": "string"}, "rationale": {"type": "string"}},
            "required": ["option_id", "rationale"]}
        shifts = {s["shift_id"]: s for s in SHIFTS}

        def val(a):
            if a.get("option_id") not in {o["id"] for o in card["options"]}:
                return ["option_id must come from get_cost_options"]
            if a["option_id"] == "run_to_failure":
                return []
            s = shifts.get(a.get("shift_id"))
            if not s:
                return [f"shift_id must be one of {sorted(shifts)}"]
            if s["starts_in_hours"] < arrival:
                return [f"shift {s['shift_id']} starts before the part arrives ({arrival} h)"]
            return []
        ans, why = self._run(case, "scheduler",
                             "You are the Scheduler agent. Pick the maintenance option and crew shift that "
                             "minimise expected cost and risk. The part must be on site before the shift.",
                             f"Schedule the repair of {case['unit_id']}.",
                             tools, ("Submit the schedule.", schema), val)

        def fallback():
            s = next((s for s in SHIFTS if s["starts_in_hours"] >= arrival), SHIFTS[-1])
            return {"option_id": card["recommended"], "shift_id": s["shift_id"],
                    "rationale": "cheapest expected-cost option, earliest shift after the part arrives"}

        def assemble(a):
            opt = next(o for o in card["options"] if o["id"] == a["option_id"])
            s = shifts.get(a.get("shift_id"))
            warn = (s and s["starts_in_hours"] > lo)
            return {"option_id": a["option_id"], "option": opt["label"], "shift": s,
                    "expected_cost_usd": opt["expected_cost_usd"], "rationale": a["rationale"],
                    "risk_note": (f"shift starts after the low end of the life estimate ({lo:.0f} h)"
                                  if warn else None),
                    "headline": f"{opt['label']}" + (f", {s['crew']} in {s['starts_in_hours']} h" if s else "")
                                + f", expected ${opt['expected_cost_usd']:,} (placeholder inputs)"}
        return self._finish(case, "scheduler", ans, why, fallback, assemble)

    def _facts(self, case):
        p, r = case["out"]["prediction"], case["results"]
        lo, hi = p["rul_range_hours"]
        lines = [f"Unit: {case['unit_id']}   Alert: {case['alert_id']}   Severity: {case['severity'].upper()}",
                 f"Risk: {p['risk']:.0%}   Estimated remaining life: {lo:.0f}-{hi:.0f} h (heuristic)"]
        if "diagnosis" in r:
            lines.append(f"Likely cause: {r['diagnosis']['root_cause']}")
        if "impact" in r:
            lines.append(f"Workloads to move first: {', '.join(r['impact']['migrate_racks']) or 'none'}")
        if "procurement" in r:
            lines.append(f"Parts: {r['procurement']['headline']}")
        if "scheduler" in r:
            lines.append(f"Plan: {r['scheduler']['headline']}")
        tpl = os.getenv("APPROVAL_URL_TEMPLATE")
        link = tpl.format(alert_id=case["alert_id"], unit_id=case["unit_id"]) if tpl else \
            f"open the maintenance dashboard and review case {case['case_id']}"
        lines += ["", "Nothing has been ordered or scheduled. Approve or reject: " + link,
                  "Prototype: simulated sensor data, parts, suppliers and prices."]
        return "\n".join(lines)

    def comms(self, case):
        facts = self._facts(case)
        allowed = _nums(facts) | _nums(json.dumps(case["results"], default=str))
        tools = {"get_case_summary": ("Everything the other agents found, plus the authoritative facts block.",
                                      {}, [], lambda a: {"facts": facts, "results": {
                                          k: v.get("headline") for k, v in case["results"].items()
                                          if isinstance(v, dict)}})}
        schema = {"type": "object", "properties": {
            "subject": {"type": "string"}, "body": {"type": "string",
                                                   "description": "short plain-text message, no sign-off"}},
            "required": ["subject", "body"]}

        def val(a):
            p = []
            if not 5 <= len(a.get("subject", "")) <= 100:
                p.append("subject must be 5-100 characters")
            bad = sorted(_nums(a.get("subject", "") + " " + a.get("body", "")) - allowed)
            if bad:
                p.append(f"numbers {bad[:5]} do not appear in the case facts; do not invent numbers")
            return p
        ans, why = self._run(case, "comms",
                             "You are the Comms agent. Write a short, plain email to the site operator explaining "
                             "what is wrong, what the crew proposes and what they must approve. No hype.",
                             f"Write the email for case {case['case_id']}.",
                             tools, ("Submit the email.", schema), val)
        sev = case["severity"].upper()

        def fallback():
            return {"subject": f"[{sev}] {case['unit_id']}: maintenance plan needs approval",
                    "body": f"The maintenance crew prepared a plan for {case['unit_id']}. Details below."}

        def assemble(a):
            return {"subject": a["subject"], "body": a["body"].strip() + "\n\n--- facts (computed, not written "
                    "by the AI) ---\n" + facts, "headline": f"email drafted: {a['subject']}"}
        return self._finish(case, "comms", ans, why, fallback, assemble)

    # ================= supervisor =================
    def _required(self, case):
        r = case["results"]
        if "triage" in r and not r["triage"]["is_unit_fault"]:
            return ["triage", "comms"]
        need = ["triage", "diagnosis", "impact", "scheduler", "comms"]
        if PARTS_STOCK.get(self._part(case), {}).get("in_stock", 1) == 0:
            need.insert(3, "procurement")
        return need

    def open_case(self, out, history, fleet=None):
        u, ts = out["unit_id"], out["tick"]["ts"]
        key = f"{u}|{out.get('alert_id')}|{ts}|{MODEL_ID}"
        if self.use_cache and key in self.cache:
            c = json.loads(json.dumps(self.cache[key]))
            c["events"] = [dict(e, message=e["message"] + " [replayed]") for e in c["events"]]
            c["out"], c["history"] = out, history
            for e in c["events"]:
                if self.on_event:
                    self.on_event(e)
            return c
        case = {"case_id": f"CASE-{out.get('alert_id', 'X')}-{u}", "unit_id": u, "alert_id": out.get("alert_id"),
                "ts": ts, "severity": out.get("severity") or "low", "status": "planning", "results": {},
                "events": [], "out": out, "history": history, "fleet": fleet or {}}
        self._ev(case, "supervisor", "running", f"opened {case['case_id']} ({case['severity'].upper()}), "
                 f"planning with {MODEL_ID}")
        runners = {"triage": self.triage, "diagnosis": self.diagnosis, "impact": self.impact,
                   "procurement": self.procurement, "scheduler": self.scheduler, "comms": self.comms}

        def call(name):
            def go(a):
                if name == "scheduler" and "procurement" in self._required(case) \
                        and "procurement" not in case["results"]:
                    self._ev(case, "supervisor", "warning", "guardrail: run procurement before scheduling "
                             "(part out of stock)")
                    return {"error": "run_procurement first: the part is out of stock"}
                if name == "comms" and any(n not in case["results"] for n in self._required(case)
                                           if n != "comms"):
                    self._ev(case, "supervisor", "warning", "guardrail: comms must run last")
                    return {"error": "run the other required specialists before comms"}
                res = runners[name](case)
                if name == "triage":
                    case["severity"] = res["severity"]
                return {k: v for k, v in res.items() if k not in ("events", "numbers", "after")} \
                    if name != "diagnosis" else {"root_cause": res["root_cause"], "confidence": res["confidence"],
                                                 "part": res.get("part"), "source": res["source"]}
            return go
        tools = {f"run_{n}": (d, {}, [], call(n)) for n, d in [
            ("triage", "Triage agent: real unit fault or site-wide? urgency."),
            ("diagnosis", "Diagnosis agent: root cause with manual citations, part needed."),
            ("impact", "Impact agent: racks at risk and workload migration plan."),
            ("procurement", "Procurement agent: stock check or draft purchase order."),
            ("scheduler", "Scheduler agent: cost option and crew shift."),
            ("comms", "Comms agent: email to the operator. Run last.")]}
        schema = {"type": "object", "properties": {
            "headline": {"type": "string", "description": "one sentence for the operator"},
            "steps": {"type": "array", "items": {"type": "string"}}}, "required": ["headline", "steps"]}
        val = lambda a: [f"run {n} before submitting" for n in self._required(case) if n not in case["results"]]
        ans, why = self._run(case, "supervisor",
                             "You are the Supervisor of a datacenter cooling maintenance crew. Run the specialist "
                             "agents you need, in a sensible order, then submit a short plan for human approval. "
                             "If triage says it is not a unit fault, skip to comms.",
                             f"Alert {case['alert_id']} on {u}, severity {case['severity']}. Build the plan.",
                             tools, ("Submit the plan for human approval.", schema), val, max_steps=12)
        if ans is None:
            self._ev(case, "supervisor", "warning", f"fixed-order fallback ({why})")
            for n in ["triage", "diagnosis", "impact", "procurement", "scheduler", "comms"]:
                if n in self._required(case) and n not in case["results"]:
                    call(n)({})
            ans = {"headline": "Plan built by the fixed-order fallback.",
                   "steps": [case["results"][n]["headline"] for n in self._required(case)]}
        case["plan"] = {"headline": ans["headline"], "steps": ans["steps"]}
        case["email"] = {k: case["results"]["comms"][k] for k in ("subject", "body")}
        case["status"] = "pending_approval"
        self._ev(case, "supervisor", "alert", f"plan ready, waiting for human approval: {ans['headline'][:120]}",
                 case["plan"])
        if self.use_cache:
            keep = {k: v for k, v in case.items() if k not in ("out", "history")}
            self.cache[key] = json.loads(json.dumps(keep, default=str))
            json.dump(self.cache, open(self.cache_path, "w"), indent=1)
        return case

    # ================= human decision, execution, verification =================
    def approve(self, case, sim=None, by="operator", now=None):
        case["status"] = "approved"
        if now:
            case["now"] = now
        self._ev(case, "human", "done", f"plan approved by {by}")
        proc = case["results"].get("procurement")
        if proc and proc["action"] == "draft_po":
            po = dict(proc, status="placed (simulated)", case_id=case["case_id"], approved_by=by,
                      placed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            open("po_log.jsonl", "a").write(json.dumps(po, default=str) + "\n")
            PARTS_STOCK[proc["part_id"]]["in_stock"] += proc["qty"]       # part arrives (time skipped in demo)
            self._ev(case, "executor", "done", f"PO placed (simulated): {proc['qty']} x {proc['part_id']} from "
                     f"{proc['supplier']}, {proc['shipping']}, ${proc['total_usd']:,}")
        sch = case["results"].get("scheduler") or {}
        open("work_orders.jsonl", "a").write(json.dumps({"case_id": case["case_id"], "unit_id": case["unit_id"],
                                                         "plan": case["plan"], "schedule": sch}, default=str) + "\n")
        self._ev(case, "executor", "done", f"work order booked (simulated): {sch.get('headline', '')}")
        mig = (case["results"].get("impact") or {}).get("migrate_racks", [])
        self._ev(case, "executor", "done", f"workloads migrated (simulated): {', '.join(mig) or 'none needed'}")
        if sim is not None:
            sim.fault_tick.pop(case["unit_id"], None)
            sim.wear[case["unit_id"]] = sim.start_wear
            part = (case["results"].get("procurement") or {}).get("part_id")
            if part in PARTS_STOCK and PARTS_STOCK[part]["in_stock"] > 0:
                PARTS_STOCK[part]["in_stock"] -= 1
            self._ev(case, "executor", "done", "repair done (simulated, time skipped to the shift); verifying")
        case["status"] = "verifying"
        return case

    def reject(self, case, by="operator", reason=""):
        case["status"] = "rejected"
        self._ev(case, "human", "warning", f"plan rejected by {by}: {reason or 'no reason given'}")
        return case

    def verify(self, case, out, history):
        u = case["unit_id"]
        case["now"] = out["tick"]["ts"]
        tools = {
            "get_sensor_history": ("Readings since the repair.", {}, [],
                                   lambda a: [{"ts": t["ts"], **t["smoothed"], "risk": t["risk"], "state": t["state"]}
                                              for t in history[-6:]]),
            "get_prediction": ("Latest risk and monitor state.", {}, [],
                               lambda a: {"risk": out["prediction"]["risk"], "threshold": out["prediction"]["threshold"],
                                          "state": out["state"], "evidence": out["prediction"]["evidence"]}),
        }
        schema = {"type": "object", "properties": {
            "verdict": {"type": "string", "enum": ["close", "keep_watching", "reopen"]},
            "rationale": {"type": "string"}}, "required": ["verdict", "rationale"]}
        val = lambda a: [] if a.get("verdict") in ("close", "keep_watching", "reopen") else ["bad verdict"]
        ans, why = self._run(case, "verifier",
                             "You are the Verifier agent. After a repair, decide if the unit is healthy again "
                             "(close), needs more readings (keep_watching), or the fix failed (reopen).",
                             f"{u} was repaired for case {case['case_id']}. Check it.",
                             tools, ("Submit the verdict.", schema), val, max_steps=4)

        def assemble(a):
            v = a["verdict"]
            if v == "close" and out["state"] != "normal":           # guardrail
                v = "keep_watching"
            note = "" if v == a["verdict"] else " (guardrail: unit not back to normal yet)"
            return {"verdict": v, "rationale": a["rationale"],
                    "headline": f"verdict {v}{note}: {a['rationale'][:90]}"}
        res = self._finish(case, "verifier", ans, why, lambda: {
            "verdict": "close" if out["state"] == "normal" else "keep_watching",
            "rationale": f"monitor state is {out['state']}"}, assemble)
        case["status"] = {"close": "closed", "reopen": "reopened"}.get(res["verdict"], "verifying")
        return res
