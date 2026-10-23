"""Model bake-off on AI4I. Same features as train.py, 5-fold stratified CV.

    python3 compare.py                 # uses data/ai4i2020.csv
    python3 compare.py --synthetic     # code test only, numbers are meaningless

Picks the winner by mean CV PR-AUC, and prints a table you can paste in the pitch.
Out-of-fold predictions are used, so no model is judged on rows it trained on.
Failure rate is ~3.4%, so ROC-AUC/accuracy would flatter everything. PR-AUC is the honest metric.
"""
import argparse
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import (ExtraTreesClassifier, HistGradientBoostingClassifier,
                              RandomForestClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .train import FEATURES, SEED, lgbm, make_synthetic, prep

warnings.filterwarnings("ignore")


def models(pos, neg):
    spw = neg / max(pos, 1)
    out = {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000)),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample",
            n_jobs=-1, random_state=SEED),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample",
            n_jobs=-1, random_state=SEED),
        "lightgbm": lgbm(pos, neg),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=10,
            class_weight="balanced", random_state=SEED),
    }
    try:
        from xgboost import XGBClassifier
        out["xgboost"] = XGBClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
            colsample_bytree=0.8, scale_pos_weight=spw, eval_metric="aucpr",
            random_state=SEED, n_jobs=-1)
    except ImportError:
        if not getattr(models, "warned", False):
            print("xgboost not installed, skipping (pip install xgboost --break-system-packages)")
            models.warned = True
    return out


def recall_at_precision(y, p, min_prec=0.5):
    prec, rec, _ = precision_recall_curve(y, p)
    ok = rec[:-1][prec[:-1] >= min_prec]
    return float(ok.max()) if len(ok) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/ai4i2020.csv")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    df = prep(make_synthetic() if a.synthetic else pd.read_csv(a.csv))
    if a.synthetic:
        print("WARNING: synthetic data, code test only.")
    X, y = df[FEATURES], df.failure.values
    print(f"rows={len(df)} failures={int(y.sum())} ({y.mean():.2%})\n")

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    rows = []
    for name, _ in models(y.sum(), (y == 0).sum()).items():
        fold_ap, oof = [], np.zeros(len(y))
        for tr, te in skf.split(X, y):
            m = models(y[tr].sum(), (y[tr] == 0).sum())[name]
            m.fit(X.iloc[tr], y[tr])
            p = m.predict_proba(X.iloc[te])[:, 1]
            oof[te] = p
            fold_ap.append(average_precision_score(y[te], p))
        rows.append({
            "model": name,
            "pr_auc_mean": np.mean(fold_ap), "pr_auc_std": np.std(fold_ap),
            "recall@prec>=0.5": recall_at_precision(y, oof),
        })
        print(f"done {name}")

    res = pd.DataFrame(rows).sort_values("pr_auc_mean", ascending=False).reset_index(drop=True)
    print("\n" + res.round(3).to_string(index=False))
    best, second = res.iloc[0], res.iloc[1]
    print(f"\nwinner: {best.model} (PR-AUC {best.pr_auc_mean:.3f} +/- {best.pr_auc_std:.3f})")
    if best.pr_auc_mean - second.pr_auc_mean < max(best.pr_auc_std, second.pr_auc_std):
        print(f"NOTE: gap to {second.model} is within fold-to-fold noise. Treat as a tie "
              "and prefer the model predict.py already supports (lightgbm).")
    res.to_csv("model_comparison.csv", index=False)
    print("saved model_comparison.csv")


if __name__ == "__main__":
    main()