"""READ-ONLY feasibility check for covering NEW cars (under 3 years old, whose next inspection is their FIRST annual test).

Question: with only make and fuel (age is the same for every vehicle at its first test), is the defect at the FIRST test predictable well enough
to justify a separate model? UK: the first MOT is at age 3; NL: at age 4. Grouped 3-fold cross-validation by vehicle, XGBoost, AUC with a bootstrap interval.
No model is exported.

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/first_test_feasibility.py   (writes ml/first_test_feasibility.json)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model2_data as md2  # noqa: E402

uk, _ = md2.uk_pairs()
nl, _ = md2.nl_pairs()
res = []
for name, d, age in (("UK first MOT (age 3)", uk, 3), ("NL first APK (age 4)", nl, 4)):
    f = d[d.age_year == age].copy()
    top = f.make.value_counts().head(40).index
    f["make_c"] = f.make.where(f.make.isin(top), "OTHER")
    cats = {"fuel": md2.FUELS, "make_c": sorted(top.tolist()) + ["OTHER"]}
    X = f[["fuel", "make_c"]].copy()
    for c in X:
        X[c] = pd.Categorical(X[c], categories=cats[c])
    for s in md2.SYSTEMS:
        y = f["cur_" + s].to_numpy()
        oof = np.zeros(len(f))
        for tri, vai in GroupKFold(n_splits=3).split(f, groups=f.unit):
            m = xgb.XGBClassifier(n_estimators=150, max_depth=3, learning_rate=0.05, min_child_weight=100, subsample=0.8, tree_method="hist", enable_categorical=True, n_jobs=8, random_state=0)
            m.fit(X.iloc[tri], y[tri])
            oof[vai] = m.predict_proba(X.iloc[vai])[:, 1]
        rng = np.random.default_rng(0)
        boots = [roc_auc_score(y[i], oof[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(100))]
        res.append({"data": name, "system": s, "n": int(len(f)), "defect_rate": float(y.mean()), "AUC (make + fuel only)": float(roc_auc_score(y, oof)), "AUC 95% interval": [float(x) for x in np.percentile(boots, [2.5, 97.5])]})
        print(res[-1], flush=True)
(ROOT / "ml" / "first_test_feasibility.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
