"""READ-ONLY: what does Model 2 add beyond the age of the vehicle?  (nothing is exported, nothing definitive is retrained)

Two test sets, the SAME for the model and for the age-only baseline:
  * UK, out of sample: 3-fold cross-fit by vehicle (the same procedure and hyper-parameters as build_risk_reference.py; these evaluation fits are NOT the exported models).
    The baseline is fitted on the same training folds: the defect rate of each age year, which is the best possible classification that uses age alone.
  * NL, independent: the EXPORTED (UK-trained) models against the baseline fitted on all UK pairs. Only the variants without odometer exist in the Dutch data.

Metrics, per system (brakes / electrical / engine-related):
  * ROC-AUC overall;
  * within-age ROC-AUC: AUC computed inside each age year (3-20) and averaged with the number of vehicles as weight. By construction an age-only baseline scores 0.50 here:
    this is the part of the ranking that does NOT come from age;
  * Recall and Precision when the 31% of vehicles with the highest score are flagged (31% = the share of the "High" level of the risk scale), and the base rate, so that the
    lift (precision / base rate) can be read. Ties of the age-only baseline are broken at random (fixed seed).

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/model2_vs_age_baseline.py   (writes ml/model2_vs_age_baseline.json)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model2_data as md2  # noqa: E402

ART = ROOT / "backend" / "app" / "ml" / "artifacts" / "model2"
card = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))
CATS, MAKES, VARIANTS, SYSTEMS = card["categories"], set(card["makes_in_training"]), card["variants"], md2.SYSTEMS
FLAG_SHARE = 0.31
GAP = 1.0
t0 = time.time()
rng = np.random.default_rng(0)


def frame(df, cols, gap=None):
    X = df[cols].copy()
    if gap is not None and "gap_next" in X:
        X["gap_next"] = gap
    for c in ("fuel", "make_c"):
        if c in X:
            X[c] = pd.Categorical(X[c], categories=CATS[c])
    return X


def age_table(train, s):
    return train.groupby("age_year")["next_" + s].mean()


def age_score(df, table):
    return df.age_year.map(table).fillna(table.mean()).to_numpy()


def flagged_metrics(y, p):
    y = np.asarray(y)
    order = np.lexsort((rng.random(len(p)), -p))            # highest score first, ties random
    k = int(round(len(p) * FLAG_SHARE))
    hit = y[order[:k]].sum()
    return {"recall": float(hit / y.sum()), "precision": float(hit / k), "base_rate": float(y.mean()), "lift": float(hit / k / y.mean())}


def within_age_auc(df, y, p):
    num = den = 0.0
    for _, g in df.groupby("age_year").groups.items():
        idx = df.index.get_indexer(g)
        yy = np.asarray(y)[idx]
        if yy.min() == yy.max() or len(idx) < 200:
            continue
        num += roc_auc_score(yy, np.asarray(p)[idx]) * len(idx)
        den += len(idx)
    return float(num / den)


def evaluate(df, y, p):
    return {"auc": float(roc_auc_score(y, p)), "within_age_auc": within_age_auc(df, y, p), **flagged_metrics(y, p)}


uk, _ = md2.uk_pairs()
nl, _ = md2.nl_pairs()
for d in (uk, nl):
    d["make_c"] = d.make.where(d.make.isin(MAKES), "OTHER")
uk = uk.reset_index(drop=True)
nl = nl.reset_index(drop=True)
print(f"[{time.time()-t0:.0f}s] UK pairs {len(uk):,} | NL pairs {len(nl):,}", flush=True)

rows = []
# ---------------- UK, out of sample (3-fold cross-fit by vehicle)
oof_model = {(v, s): np.zeros(len(uk)) for v in VARIANTS for s in SYSTEMS}
oof_age = {s: np.zeros(len(uk)) for s in SYSTEMS}
for tri, vai in GroupKFold(n_splits=3).split(uk, groups=uk.unit):
    for s in SYSTEMS:
        oof_age[s][vai] = age_score(uk.iloc[vai], age_table(uk.iloc[tri], s))
        for v, cols in VARIANTS.items():
            m = xgb.XGBClassifier(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist", enable_categorical=True, n_jobs=8, random_state=0, eval_metric="logloss", **card["hyperparameters"][f"{s}/{v}"])
            m.fit(frame(uk.iloc[tri], cols), uk.iloc[tri]["next_" + s])
            oof_model[(v, s)][vai] = m.predict_proba(frame(uk.iloc[vai], cols, gap=GAP))[:, 1]
    print(f"[{time.time()-t0:.0f}s] fold done", flush=True)
for s in SYSTEMS:
    y = uk["next_" + s].to_numpy()
    rows.append({"test_set": "UK out-of-sample (3-fold by vehicle)", "system": s, "model": "age only", **evaluate(uk, y, oof_age[s])})
    for v in VARIANTS:
        rows.append({"test_set": "UK out-of-sample (3-fold by vehicle)", "system": s, "model": f"XGBoost {v}", **evaluate(uk, y, oof_model[(v, s)])})

# ---------------- NL, independent: exported models against the baseline fitted on all UK pairs
for s in SYSTEMS:
    y = nl["next_" + s].to_numpy()
    rows.append({"test_set": "NL independent (UK-trained)", "system": s, "model": "age only", **evaluate(nl, y, age_score(nl, age_table(uk, s)))})
    for v in ("cold", "hist"):
        b = xgb.Booster()
        b.load_model(str(ART / f"{v}_{s}.json"))
        p = b.predict(xgb.DMatrix(frame(nl, VARIANTS[v], gap=GAP), enable_categorical=True))
        rows.append({"test_set": "NL independent (UK-trained)", "system": s, "model": f"XGBoost {v} (exported)", **evaluate(nl, y, p)})

out = {"flag_share": FLAG_SHARE, "uk_pairs": int(len(uk)), "nl_pairs": int(len(nl)), "rows": rows}
(ROOT / "ml" / "model2_vs_age_baseline.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
df = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(df.assign(**{c: df[c].round(3) for c in ("auc", "within_age_auc", "recall", "precision", "base_rate", "lift")}).to_string(index=False))
print(f"[{time.time()-t0:.0f}s] written ml/model2_vs_age_baseline.json", flush=True)
