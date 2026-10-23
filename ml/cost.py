"""Expected-cost decision card. Deterministic, no LLM.
DOLLAR INPUTS ARE ILLUSTRATIVE PLACEHOLDERS, not data. The customer replaces them.

    from cost import estimate
    card = estimate(out)                                       # out = AlertManager output
    card = estimate(out, assumptions={"downtime_cost_per_hour": 25000})

Chance of failing before the fix comes from the (heuristic) remaining-life range:
5% at the low end, 95% at the high end. Earliest fix = max(crew time, part arrival).
Expected cost = P(fail first) x unplanned cost + (1 - P) x planned cost (+ expedite fee).
"""
try:
    from diagnosis import PARTS_STOCK
except Exception:
    PARTS_STOCK = {"BRG-6205": {"name": "Fan motor bearing assembly", "in_stock": 0, "lead_time_days": 3,
                                "expedite_days": 1, "expedite_fee_usd": 450}}

DEFAULTS = {
    "downtime_cost_per_hour": 10000, "outage_hours": 4, "collateral_damage_usd": 3000,
    "part_cost_usd": 1800, "planned_labor_usd": 600, "emergency_labor_usd": 1200,
    "migration_cost_usd": 500, "tonight_hours": 6, "next_window_hours": 36,
}
P_FLOOR, P_CEIL = 0.05, 0.95


def p_fail_before(t_h, lo, hi):
    if t_h is None or t_h >= hi:
        return P_CEIL
    if t_h <= lo:
        return P_FLOOR
    return P_FLOOR + (P_CEIL - P_FLOOR) * (t_h - lo) / max(hi - lo, 1e-6)


def estimate(out, assumptions=None):
    pred, rec = out["prediction"], out.get("recommendation") or {}
    a = dict(DEFAULTS, **(assumptions or {}))
    lo, hi = pred["rul_range_hours"]
    stock = PARTS_STOCK.get(rec.get("part_id"), {})
    in_stock = stock.get("in_stock", 1) > 0 if stock else True
    lead_h = 0 if in_stock else stock.get("lead_time_days", 3) * 24
    exp_h = 0 if in_stock else stock.get("expedite_days", 1) * 24
    fee = 0 if in_stock else stock.get("expedite_fee_usd", 0)

    unplanned = (a["outage_hours"] * a["downtime_cost_per_hour"] + a["collateral_damage_usd"]
                 + a["part_cost_usd"] + a["emergency_labor_usd"])
    planned = a["part_cost_usd"] + a["planned_labor_usd"] + a["migration_cost_usd"]

    def fix_option(oid, label, t, fee_usd, note):
        p = p_fail_before(t, lo, hi)
        exp = p * unplanned + (1 - p) * planned + fee_usd
        return {"id": oid, "label": label, "fix_in_hours": round(t, 1), "p_fail_first": round(p, 2),
                "if_it_fails_usd": round(unplanned + fee_usd), "if_it_holds_usd": round(planned + fee_usd),
                "expedite_fee_usd": fee_usd, "expected_cost_usd": round(exp), "note": note}

    t_early = max(a["tonight_hours"], exp_h)
    t_window = max(a["next_window_hours"], lead_h)
    options = [
        {"id": "run_to_failure", "label": "Keep running until it fails", "fix_in_hours": None,
         "p_fail_first": P_CEIL, "if_it_fails_usd": round(unplanned), "if_it_holds_usd": 0,
         "expedite_fee_usd": 0, "expected_cost_usd": round(P_CEIL * unplanned),
         "note": "Unplanned outage plus emergency call-out. Chance capped at 95% because the life range is a heuristic."},
        fix_option("fix_now", "Fix tonight" if in_stock else "Fix as soon as the part arrives (expedite)",
                   t_early, fee,
                   "Part in stock." if in_stock else
                   f"Part out of stock: expedite adds {fee} USD and arrives in about {exp_h} h."),
        fix_option("fix_next_window", "Wait for the next planned window", t_window, 0,
                   f"Standard part lead time{'' if in_stock else f' ({lead_h} h)'} and the next window "
                   f"({a['next_window_hours']} h)."),
    ]
    best = min(options, key=lambda o: o["expected_cost_usd"])
    base = options[0]["expected_cost_usd"]
    saving = base - best["expected_cost_usd"]
    card = {
        "unit_id": out["unit_id"], "alert_id": out.get("alert_id"), "severity": out.get("severity"),
        "options": options, "recommended": best["id"], "saving_vs_run_to_failure_usd": saving,
        "life_range_hours": [lo, hi],
        "assumptions": dict(a, source="PLACEHOLDERS, replace with the customer's real numbers",
                            p_fail_rule=f"{P_FLOOR:.0%} at {lo:.0f} h rising to {P_CEIL:.0%} at {hi:.0f} h "
                                        "(heuristic life range)"),
        "disclaimer": "Illustrative estimate from placeholder inputs. Not a quote or a guarantee.",
    }
    card["events"] = [{
        "ts": out["tick"]["ts"], "agent": "scheduler", "status": "done",
        "message": (f"{out['unit_id']}: cheapest option is '{best['label']}', expected "
                    f"${best['expected_cost_usd']:,} vs ${base:,} to run to failure (placeholder inputs)"),
        "data": {"recommended": best["id"], "saving_usd": saving}}]
    return card


if __name__ == "__main__":
    from alerts import AlertManager
    from monitor import Monitor
    from simulator import Simulator
    sim, mon, am = Simulator(), Monitor(), AlertManager(outbox="outbox_demo.jsonl")
    hit = None
    for k in range(48):
        if k == 12:
            sim.inject("CRAC-3")
        for r in sim.step():
            o = am.process(mon.process(r))
            if r["unit_id"] == "CRAC-3" and o.get("severity") == "high" and hit is None:
                hit = o
    card = estimate(hit)
    print(f"{card['unit_id']} {card['severity']}, life {card['life_range_hours']} h\n")
    for o in card["options"]:
        star = "  <-- recommended" if o["id"] == card["recommended"] else ""
        fix = f"{o['fix_in_hours']} h" if o["fix_in_hours"] is not None else "never"
        print(f"{o['label']:<48} fix in {fix:<7} P(fail first) {o['p_fail_first']:.0%}  "
              f"expected ${o['expected_cost_usd']:>7,}{star}")
    print(f"\nsaves ${card['saving_vs_run_to_failure_usd']:,} vs running to failure (placeholder inputs)")
    print(card["events"][0]["message"])
