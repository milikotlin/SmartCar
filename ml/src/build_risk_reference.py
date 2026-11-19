"""Builds the REFERENCE SCALE of the Model 2 risk indicators. The exported boosters are NOT retrained or modified.

What it does
  1. Cross-fits (3 folds by vehicle, same hyper-parameters as the exported models) every variant and system on the UK pairs and scores each held-out fold
     twice: with the realised interval to the next inspection (how the models were evaluated) and with the interval STANDARDISED to 12 months (how the
     indicators are now computed). The two are compared (ROC-AUC, capture) to show that standardising does not hurt.
  2. Stores the out-of-sample UK scores as the reference distribution: 101 quantiles per variant and system (all ages 3-20) and the deciles per age.
  3. Chooses the three risk levels (Low / Moderate / High) from the data: the cut points, as percentiles of the reference distribution, that best describe
     the observed defects (maximum log-likelihood of a three-level step function), with each level holding at least 20% of the reference vehicles. Common cut
     points for the three systems are used if they lose almost nothing against per-system optima. Observed defect rates per level are computed on the UK
     (cross-fitted) and, independently, on the Dutch data scored by the UK-trained exported models.
  4. Writes backend/app/ml/artifacts/model2/model2_reference.json.

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/build_risk_reference.py
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
CATS, MAKES = card["categories"], set(card["makes_in_training"])
SYSTEMS = md2.SYSTEMS
VARIANTS = card["variants"]
STANDARD_GAP = 1.0
t0 = time.time()


def frame(df, cols, gap=None):
    X = df[cols].copy()
    if gap is not None and "gap_next" in X:
        X["gap_next"] = gap
    for c in ("fuel", "make_c"):
        if c in X:
            X[c] = pd.Categorical(X[c], categories=CATS[c])
    return X


def capture(y, p, frac=0.2):
    k = int(len(p) * frac)
    idx = np.argsort(-p)[:k]
    return float(np.asarray(y)[idx].sum() / np.sum(y))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return (float((c - h) / d), float((c + h) / d))


uk, _ = md2.uk_pairs()
nl, _ = md2.nl_pairs()
for d in (uk, nl):
    d["make_c"] = d.make.where(d.make.isin(MAKES), "OTHER")
print(f"[{time.time()-t0:.0f}s] UK pairs {len(uk):,} | NL pairs {len(nl):,}", flush=True)

# ------------------------------------------------------------------ 1. cross-fitted scores, realised and standardised interval
oof_std, oof_real, perf = {}, {}, []
for v, cols in VARIANTS.items():
    for s in SYSTEMS:
        params = card["hyperparameters"][f"{s}/{v}"]
        a, b = np.zeros(len(uk)), np.zeros(len(uk))
        for tri, vai in GroupKFold(n_splits=3).split(uk, groups=uk.unit):
            m = xgb.XGBClassifier(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist", enable_categorical=True, n_jobs=8, random_state=0, eval_metric="logloss", **params)
            m.fit(frame(uk.iloc[tri], cols), uk.iloc[tri]["next_" + s])
            a[vai] = m.predict_proba(frame(uk.iloc[vai], cols, gap=STANDARD_GAP))[:, 1]
            b[vai] = m.predict_proba(frame(uk.iloc[vai], cols))[:, 1]
        oof_std[(v, s)], oof_real[(v, s)] = a, b
        y = uk["next_" + s].to_numpy()
        perf.append({"variant": v, "system": s, "UK cross-fitted AUC, realised interval": float(roc_auc_score(y, b)), "UK cross-fitted AUC, standardised 12 months": float(roc_auc_score(y, a)),
                     "capture top20 realised": capture(y, b), "capture top20 standardised": capture(y, a)})
        print(f"[{time.time()-t0:.0f}s] cross-fit {v}/{s}: AUC realised {perf[-1]['UK cross-fitted AUC, realised interval']:.4f} standardised {perf[-1]['UK cross-fitted AUC, standardised 12 months']:.4f}", flush=True)

# exported boosters on the Dutch data (independent, out of sample); only variants without odometer exist there
boosters = {}
for v in VARIANTS:
    for s in SYSTEMS:
        bst = xgb.Booster()
        bst.load_model(str(ART / f"{v}_{s}.json"))
        boosters[(v, s)] = bst
nl_scores = {}
for v in ("cold", "hist"):
    for s in SYSTEMS:
        dm_std = xgb.DMatrix(frame(nl, VARIANTS[v], gap=STANDARD_GAP), enable_categorical=True)
        dm_real = xgb.DMatrix(frame(nl, VARIANTS[v]), enable_categorical=True)
        nl_scores[(v, s)] = boosters[(v, s)].predict(dm_std)
        y = nl["next_" + s].to_numpy()
        perf.append({"variant": v + " (NL, UK-trained exported models)", "system": s, "UK cross-fitted AUC, realised interval": float(roc_auc_score(y, boosters[(v, s)].predict(dm_real))),
                     "UK cross-fitted AUC, standardised 12 months": float(roc_auc_score(y, nl_scores[(v, s)]))})

# ------------------------------------------------------------------ 2. reference distribution
Q = np.linspace(0, 1, 101)
reference_quantiles, same_age = {}, {}
for (v, s), p in oof_std.items():
    reference_quantiles[f"{v}/{s}"] = [float(x) for x in np.quantile(p, Q)]
    levels = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    dq = pd.DataFrame({"a": uk.age_year.to_numpy(), "p": p}).groupby("a").p.quantile(levels).unstack()
    same_age[f"{v}/{s}"] = {str(a): [float(x) for x in dq.loc[a, levels]] for a in dq.index}


def rank_pct(ref_sorted, x):
    return np.searchsorted(ref_sorted, x, side="right") / len(ref_sorted) * 100


# ------------------------------------------------------------------ 3. choose the three levels from observed defect rates (cold variant: the most common situation)
def percentile_bins(rank, y):
    """defects and vehicles in each 1%-wide percentile bin (bin 0 = ranks (0,1])"""
    idx = np.clip(np.ceil(rank).astype(int) - 1, 0, 99)
    n = np.bincount(idx, minlength=100).astype(float)
    k = np.bincount(idx, weights=y, minlength=100)
    return n, k


def loglik(k, n):
    out = 0.0
    if 0 < k < n:
        out = k * np.log(k / n) + (n - k) * np.log(1 - k / n)
    return out


grids = {}
for s in SYSTEMS:
    p = oof_std[("cold", s)]
    ref_sorted = np.sort(p)
    y = uk["next_" + s].to_numpy()
    n, k = percentile_bins(rank_pct(ref_sorted, p), y)
    grids[s] = (np.cumsum(n), np.cumsum(k))
total_ll = {}
cands = [(a, b) for a in range(20, 61) for b in range(a + 20, 81)]       # each level holds at least 20% of the reference vehicles (High at least 20%: b <= 80)


def ll_for(s, a, b):
    cn, ck = grids[s]
    nl_, kl = cn[a - 1], ck[a - 1]
    nm, km = cn[b - 1] - cn[a - 1], ck[b - 1] - ck[a - 1]
    nh, kh = cn[-1] - cn[b - 1], ck[-1] - ck[b - 1]
    return loglik(kl, nl_) + loglik(km, nm) + loglik(kh, nh)


per_system = {}
for s in SYSTEMS:
    scores = {(a, b): ll_for(s, a, b) for a, b in cands}
    best = max(scores, key=scores.get)
    base = loglik(grids[s][1][-1], grids[s][0][-1])
    per_system[s] = {"best_cuts": best, "loglik_gain_vs_no_split": float(scores[best] - base), "scores": scores, "base": base}
common_scores = {c: sum(ll_for(s, *c) for s in SYSTEMS) for c in cands}
common = max(common_scores, key=common_scores.get)
loss = {s: float((per_system[s]["scores"][per_system[s]["best_cuts"]] - per_system[s]["scores"][common]) / per_system[s]["loglik_gain_vs_no_split"]) for s in SYSTEMS}
print(f"[{time.time()-t0:.0f}s] per-system optimal cuts {({s: per_system[s]['best_cuts'] for s in SYSTEMS})}; common optimum {common}; share of the log-likelihood gain lost by using the common cuts {({s: round(v, 4) for s, v in loss.items()})}", flush=True)
use_common = max(loss.values()) <= 0.02
cuts = {s: (common if use_common else per_system[s]["best_cuts"]) for s in SYSTEMS}
# a coarser, easier-to-state alternative is evaluated too (rounded to multiples of 5)
rounded = tuple(int(5 * round(c / 5)) for c in common)
rounded_loss = {s: float((per_system[s]["scores"][per_system[s]["best_cuts"]] - ll_for(s, *rounded)) / per_system[s]["loglik_gain_vs_no_split"]) for s in SYSTEMS}

# ------------------------------------------------------------------ 4. observed defect rates per level (UK cross-fitted, and Dutch independent)
def level_of(rank, a, b):
    return np.where(rank <= a, 0, np.where(rank <= b, 1, 2))


level_rates = []
for (v, s), p in oof_std.items():
    a, b = cuts[s]
    ref_sorted = np.sort(p)
    y = uk["next_" + s].to_numpy()
    lv = level_of(rank_pct(ref_sorted, p), a, b)
    row = {"variant": v, "system": s, "data": "UK cross-fitted", "base_rate": float(y.mean())}
    for i, name in enumerate(("low", "moderate", "high")):
        kk, nn = int(y[lv == i].sum()), int((lv == i).sum())
        row[name] = {"share": nn / len(y), "rate": kk / nn, "ci95": wilson(kk, nn), "mean_age": float(uk.age_year.to_numpy()[lv == i].mean())}
    level_rates.append(row)
for (v, s), p in nl_scores.items():
    a, b = cuts[s]
    ref_sorted = np.sort(oof_std[(v, s)])
    y = nl["next_" + s].to_numpy()
    lv = level_of(rank_pct(ref_sorted, p), a, b)
    row = {"variant": v, "system": s, "data": "NL (independent, UK-trained models)", "base_rate": float(y.mean())}
    for i, name in enumerate(("low", "moderate", "high")):
        kk, nn = int(y[lv == i].sum()), int((lv == i).sum())
        row[name] = {"share": nn / len(y), "rate": (kk / nn) if nn else None, "ci95": wilson(kk, nn), "mean_age": float(nl.age_year.to_numpy()[lv == i].mean()) if nn else None}
    level_rates.append(row)

# alternative cut sets for the justification table (cold variant, UK and NL)
alt_rows = []
for name, cs in (("chosen", None), ("30/70", (30, 70)), ("33/67", (33, 67)), ("20/80", (20, 80)), ("40/80", (40, 80))):
    for s in SYSTEMS:
        a, b = cuts[s] if cs is None else cs
        for data, pp, ref, yy in (("UK", oof_std[("cold", s)], oof_std[("cold", s)], uk["next_" + s].to_numpy()), ("NL", nl_scores[("cold", s)], oof_std[("cold", s)], nl["next_" + s].to_numpy())):
            lv = level_of(rank_pct(np.sort(ref), pp), a, b)
            r = [float(yy[lv == i].mean()) if (lv == i).any() else None for i in range(3)]
            alt_rows.append({"cuts": name, "applied": [a, b], "system": s, "data": data, "rates": r, "shares": [float((lv == i).mean()) for i in range(3)]})

OUT = {
    "version": "1.1.0",
    "built_on": time.strftime("%Y-%m-%d"),
    "reference_population": "UK MOT pairs 2022 -> 2023, out-of-sample (3-fold cross-fitted by vehicle) scores, all ages 3-20, petrol/diesel/hybrid, interval to the next inspection standardised to 12 months",
    "standard_gap_years": STANDARD_GAP,
    "quantile_levels": [float(x) for x in Q],
    "reference_quantiles": reference_quantiles,
    "same_age_score_deciles": same_age,
    "decile_levels": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "level_cut_percentiles": {s: list(map(int, cuts[s])) for s in SYSTEMS},
    "level_selection": {
        "criterion": "maximum log-likelihood of a three-level step function of the observed defects (UK cross-fitted, cold variant), each level holding at least 20% of the reference vehicles",
        "per_system_optimum": {s: list(map(int, per_system[s]["best_cuts"])) for s in SYSTEMS}, "common_optimum": list(map(int, common)),
        "share_of_gain_lost_with_common_cuts": loss, "common_cuts_used": bool(use_common), "rounded_to_5": list(rounded), "share_of_gain_lost_with_rounded_cuts": rounded_loss,
    },
    "level_rates": level_rates,
    "alternative_cuts": alt_rows,
    "interval_standardisation_check": perf,
    "same_age_bands": {"lower": "below the 20th percentile of vehicles of the same age", "higher": "above the 80th percentile of vehicles of the same age"},
}
(ART / "model2_reference.json").write_text(json.dumps(OUT, indent=1), encoding="utf-8")
print(f"[{time.time()-t0:.0f}s] written {ART / 'model2_reference.json'}", flush=True)
