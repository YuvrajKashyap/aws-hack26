"""predict(reading) -> prediction dict, matching the shared contract.

Sensor reading in:  {"unit_id","rpm","torque","vibration","temp_c","power_kw","lube_ppm","tool_wear_min", ...}
Prediction out:     {"unit_id","risk","rul_hours","confidence","failure_mode","evidence", ...extras}

HONEST LABELS (say these in the pitch):
- model_risk is a calibrated HistGradientBoosting probability trained on AI4I 2020, using only
  rpm, torque, temperature, tool wear (mapped from CRAC signals, an analogy).
- vibration and lube are NOT in AI4I. They feed a rule-based heuristic risk (vs a healthy
  baseline). Final risk = max(model_risk, heuristic_risk). risk_kind says which one won.
- rul_hours is a wear-threshold projection (AI4I tool wear fails ~200-240 min), not a
  validated remaining-useful-life model. There are no run-to-failure labels.
"""
import functools

import joblib
import numpy as np
import pandas as pd

from train import FEATURES, featurize

# ---- mapping assumptions: edit these to match the simulator's healthy values ----
AMBIENT_K = 300.0          # AI4I air temperature, held constant
HEALTHY_TEMP_C = 45.0      # healthy CRAC motor temp that maps to AI4I process temp 310 K
HEALTHY_PROCESS_K = 310.0
VIB_BASE = 2.0             # healthy vibration (mm/s RMS) in the simulator
LUBE_BASE = 12.0           # healthy lube wear-metal ppm in the simulator
WEAR_MIN_PER_HOUR = 3.0    # how fast the simulator ages tool_wear_min (demo assumption)
WEAR_FAIL_MIN, WEAR_FAIL_MAX = 200.0, 240.0   # AI4I tool-wear failure window

MODE_LABELS = {  # AI4I mode -> CRAC-facing label. This mapping is OUR analogy.
    "TWF": "bearing_wear",
    "HDF": "heat_dissipation_fault",
    "PWF": "motor_power_fault",
    "OSF": "overstrain_fault",
}
NICE = {"air_k": "ambient temp", "process_k": "motor temp", "rpm": "fan speed",
        "torque": "torque", "wear": "wear hours-equivalent", "power_w": "mechanical power",
        "temp_gap": "temp rise over ambient", "strain": "wear x torque strain",
        "type_L": "class L", "type_M": "class M", "type_H": "class H"}


RAW_IN = ["air_k", "process_k", "rpm", "torque", "wear"]


def _contributions(b, X, p0):
    """Drop in raw model score when each raw input is reset to its typical (median) value.
    Positive = that input pushes risk up. Works for any model; derived features are rebuilt."""
    typ = next(k for k in "LMH" if X.iloc[0][f"type_{k}"] == 1)
    base = {c: float(X.iloc[0][c]) for c in RAW_IN}
    out = {}
    for c in RAW_IN:
        row = dict(base, Type=typ)
        row[c] = b["medians"][c]
        out[c] = p0 - float(b["model"].predict_proba(featurize(pd.DataFrame([row]))[FEATURES])[:, 1][0])
    return out


@functools.lru_cache(maxsize=1)
def _bundle(path="model.joblib"):
    return joblib.load(path)


def to_ai4i(r):
    """Map a CRAC sensor reading onto the AI4I feature columns."""
    row = {
        "air_k": AMBIENT_K,
        "process_k": HEALTHY_PROCESS_K + (float(r["temp_c"]) - HEALTHY_TEMP_C),
        "rpm": float(r["rpm"]), "torque": float(r["torque"]),
        "wear": float(r["tool_wear_min"]), "Type": r.get("class", "M"),
    }
    return featurize(pd.DataFrame([row]))[FEATURES]


def _ramp(ratio, lo=1.3, hi=2.4, top=0.9):
    """Healthy-baseline drift rule: 0 below lo x baseline, `top` at hi x baseline."""
    return float(np.clip((ratio - lo) / (hi - lo), 0, 1) * top)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def predict(reading, path="model.joblib"):
    b = _bundle(path)
    X = to_ai4i(reading)
    raw = b["model"].predict_proba(X)[:, 1]
    model_risk = float(b["platt"].predict_proba(_logit(raw))[:, 1][0])

    vib_ratio = float(reading.get("vibration", VIB_BASE)) / VIB_BASE
    lube_ratio = float(reading.get("lube_ppm", LUBE_BASE)) / LUBE_BASE
    vib_risk, lube_risk = _ramp(vib_ratio), _ramp(lube_ratio, 1.5, 3.0, 0.7)
    heur_risk = max(vib_risk, lube_risk)
    risk = max(model_risk, heur_risk)
    risk_kind = "heuristic_drift_rule" if heur_risk > model_risk else "calibrated_model"

    # failure mode
    if heur_risk > model_risk and heur_risk >= 0.3:
        mode = "bearing_wear"
    else:
        probs = {m: float(c.predict_proba(X)[:, 1][0]) for m, c in b["modes"].items()}
        top = max(probs, key=probs.get) if probs else None
        mode = MODE_LABELS.get(top, "no_fault") if probs and probs[top] >= 0.2 else "no_fault"
        if mode == "no_fault" and risk >= b["threshold"]:
            mode = "bearing_wear" if reading["tool_wear_min"] >= WEAR_FAIL_MIN else "overstrain_fault"

    # RUL: wear-threshold projection, shortened when drift is high. Heuristic, not validated.
    wear = float(reading["tool_wear_min"])
    shrink = 1 - 0.5 * heur_risk
    rul = max(0.0, (WEAR_FAIL_MAX - wear) / WEAR_MIN_PER_HOUR * shrink)
    rul_lo = max(0.0, (WEAR_FAIL_MIN - wear) / WEAR_MIN_PER_HOUR * shrink)

    # evidence: inputs whose reset to typical lowers the model score most, plus drift rules
    contrib = _contributions(b, X, float(raw[0]))
    order = sorted(contrib, key=contrib.get, reverse=True)
    ev = []
    for f in (order[:3] if model_risk >= 0.1 else []):
        if contrib[f] <= 0.05:
            break
        ev.append(f"{NICE[f]} {X.iloc[0][f]:.1f} vs typical {b['medians'][f]:.1f} raises risk")
    if vib_ratio >= 1.3:
        ev.insert(0, f"vibration {vib_ratio - 1:+.0%} vs healthy baseline (rule)")
    if lube_ratio >= 1.5:
        ev.insert(0, f"lube wear-metal {lube_ratio - 1:+.0%} vs healthy baseline (rule)")
    if not ev:
        ev = ["all channels within healthy range"]

    return {
        "unit_id": reading.get("unit_id", "unknown"),
        "risk": round(risk, 3),
        "rul_hours": round(rul, 1),
        "confidence": round(max(risk, 1 - risk), 3),  # how sure of the final call (not accuracy)
        "failure_mode": mode,
        "evidence": ev[:4],
        # extras: show these in the UI "assumptions" panel
        "risk_kind": risk_kind, "model_risk": round(model_risk, 3),
        "heuristic_risk": round(heur_risk, 3), "threshold": round(b["threshold"], 3),
        "rul_range_hours": [round(rul_lo, 1), round(rul, 1)],
        "rul_method": "wear-threshold projection (heuristic, not validated RUL)",
    }


if __name__ == "__main__":
    import json
    ok = {"unit_id": "CRAC-3", "rpm": 1450, "torque": 38.0, "vibration": 2.0,
          "temp_c": 45.0, "power_kw": 7.0, "lube_ppm": 12, "tool_wear_min": 60}
    bad = dict(ok, vibration=4.6, temp_c=52.0, torque=55.0, lube_ppm=30, tool_wear_min=135)
    for name, r in [("normal", ok), ("fault", bad)]:
        print(name, json.dumps(predict(r), indent=2))