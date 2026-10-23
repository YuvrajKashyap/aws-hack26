"""Train the failure-risk model on AI4I 2020.

Usage:
    python3 train.py                      # uses data/ai4i2020.csv
    python3 train.py --csv path/to.csv
    python3 train.py --synthetic          # AI4I-style fake data, for testing the code only

Outputs model.joblib (used by predict.py) and metrics.json (for the pitch).
Do not pass temperature anywhere in the Bedrock code; this file has no LLM calls.
"""
import argparse
import json
import sys

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             precision_recall_curve, precision_score,
                             recall_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

SEED = 42
MODES = ["TWF", "HDF", "PWF", "OSF"]  # RNF is random by construction, skipped
RAW = ["air_k", "process_k", "rpm", "torque", "wear"]
FEATURES = RAW + ["type_L", "type_M", "type_H", "power_w", "temp_gap", "strain"]


def make_synthetic(n=10000, seed=SEED):
    """AI4I-style data built from the published failure rules. Test use only."""
    r = np.random.default_rng(seed)
    t = r.choice(["L", "M", "H"], size=n, p=[0.6, 0.3, 0.1])
    air = 300 + np.cumsum(r.normal(0, 0.05, n)) % 4 - 2 + r.normal(0, 0.3, n)
    proc = air + 10 + r.normal(0, 1.0, n)
    rpm = (2860 / np.clip(r.normal(1.8, 0.35, n), 1.0, None)).round()
    torque = r.normal(40, 10, n).clip(3, 76)
    wear = r.integers(0, 254, n).astype(float)
    power = torque * rpm * 2 * np.pi / 60
    lim = pd.Series(t).map({"L": 11000, "M": 12000, "H": 13000}).values
    twf = ((wear >= 200) & (wear <= 240) & (r.random(n) < 0.15)).astype(int)
    hdf = (((proc - air) < 8.6) & (rpm < 1380)).astype(int)
    pwf = ((power < 3500) | (power > 9000)).astype(int)
    osf = ((wear * torque) > lim).astype(int)
    rnf = (r.random(n) < 0.001).astype(int)
    mf = ((twf + hdf + pwf + osf + rnf) > 0).astype(int)
    return pd.DataFrame({
        "UDI": np.arange(1, n + 1), "Product ID": [f"{x}{i}" for i, x in enumerate(t)],
        "Type": t, "Air temperature [K]": air, "Process temperature [K]": proc,
        "Rotational speed [rpm]": rpm, "Torque [Nm]": torque, "Tool wear [min]": wear,
        "Machine failure": mf, "TWF": twf, "HDF": hdf, "PWF": pwf, "OSF": osf, "RNF": rnf})


def prep(df):
    """Rename columns, build features. Failure flags and IDs are NEVER features."""
    df = df.rename(columns={
        "Air temperature [K]": "air_k", "Process temperature [K]": "process_k",
        "Rotational speed [rpm]": "rpm", "Torque [Nm]": "torque",
        "Tool wear [min]": "wear", "Machine failure": "failure"})
    for c in ["air_k", "process_k", "rpm", "torque", "wear", "failure"] + MODES:
        if c not in df.columns:
            sys.exit(f"missing column: {c}. Columns found: {list(df.columns)}")
    return featurize(df)


def featurize(df):
    out = df.copy()
    for k in "LMH":
        out[f"type_{k}"] = (out["Type"] == k).astype(int) if "Type" in out else 0
    out["power_w"] = out["torque"] * out["rpm"] * 2 * np.pi / 60
    out["temp_gap"] = out["process_k"] - out["air_k"]
    out["strain"] = out["wear"] * out["torque"]
    return out


def lgbm(pos, neg):
    return lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=10,
        subsample=0.8, colsample_bytree=0.8, subsample_freq=1,
        scale_pos_weight=neg / max(pos, 1), random_state=SEED, verbose=-1)


def hgb():
    """Main failure-risk model. Won the 5-fold CV bake-off (compare.py) on PR-AUC."""
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=10,
        class_weight="balanced", random_state=SEED)


def pick_threshold(y, p, min_precision=0.5):
    """Highest-recall threshold whose precision stays >= min_precision (chosen on val)."""
    prec, rec, thr = precision_recall_curve(y, p)
    ok = [(rec[i], thr[i]) for i in range(len(thr)) if prec[i] >= min_precision]
    return float(max(ok)[1]) if ok else 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/ai4i2020.csv")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    df = make_synthetic() if a.synthetic else pd.read_csv(a.csv)
    if a.synthetic:
        print("WARNING: synthetic data. Metrics below are NOT results. Code test only.")
    df = prep(df)
    print(f"rows={len(df)} failures={int(df.failure.sum())} ({df.failure.mean():.2%})")

    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=0.2, stratify=df.failure, random_state=SEED)
    tr, va = train_test_split(tr, test_size=0.25, stratify=df.failure.iloc[tr], random_state=SEED)
    X, y = df[FEATURES], df.failure.values

    # Baseline: scaled logistic regression
    sc = StandardScaler().fit(X.iloc[tr])
    base = LogisticRegression(class_weight="balanced", max_iter=1000).fit(sc.transform(X.iloc[tr]), y[tr])
    p_base = base.predict_proba(sc.transform(X.iloc[te]))[:, 1]

    # Main: HistGradientBoosting, then Platt calibration fitted on the validation split
    model = hgb().fit(X.iloc[tr], y[tr])
    raw_va = model.predict_proba(X.iloc[va])[:, 1]
    logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    platt = LogisticRegression().fit(logit(raw_va), y[va])
    cal = lambda Xs: platt.predict_proba(logit(model.predict_proba(Xs)[:, 1]))[:, 1]
    thr = pick_threshold(y[va], cal(X.iloc[va]))
    p_te = cal(X.iloc[te])
    pred = (p_te >= thr).astype(int)

    metrics = {
        "data": "synthetic" if a.synthetic else a.csv, "main_model": "hist_gradient_boosting",
        "n_train": len(tr), "n_val": len(va), "n_test": len(te),
        "test_failures": int(y[te].sum()), "threshold": thr,
        "main_pr_auc": float(average_precision_score(y[te], p_te)),
        "main_precision": float(precision_score(y[te], pred, zero_division=0)),
        "main_recall": float(recall_score(y[te], pred)),
        "main_confusion[tn,fp,fn,tp]": confusion_matrix(y[te], pred).ravel().tolist(),
        "baseline_logreg_pr_auc": float(average_precision_score(y[te], p_base)),
    }

    # Failure-mode models (trained on train+val, no threshold needed, argmax at inference)
    fit_idx = np.concatenate([tr, va])
    modes = {}
    for m in MODES:
        ym = df[m].values
        if ym[fit_idx].sum() < 5:
            print(f"skip {m}: too few positives")
            continue
        modes[m] = lgbm(ym[fit_idx].sum(), (ym[fit_idx] == 0).sum()).fit(X.iloc[fit_idx], ym[fit_idx])

    medians = X.iloc[tr].median().to_dict()
    joblib.dump({"model": model, "platt": platt, "threshold": thr, "modes": modes,
                 "features": FEATURES, "medians": medians}, "model.joblib")
    json.dump(metrics, open("metrics.json", "w"), indent=2)
    print(json.dumps(metrics, indent=2))
    print("saved model.joblib and metrics.json")


if __name__ == "__main__":
    main()