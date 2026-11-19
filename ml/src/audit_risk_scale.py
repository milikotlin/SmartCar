"""READ-ONLY audit of how Model 2 risk indicators are computed and displayed. Does not train, export or modify anything: it only loads the exported
boosters and the data, recomputes cross-fitted scores for the 'cold' variant (same hyper-parameters as the exported models) and writes ml/audit_risk_scale_results.json.

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/audit_risk_scale.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model2_data as md2  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402

ART = ROOT / "backend" / "app" / "ml" / "artifacts" / "model2"
card = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))
CATS = card["categories"]
MAKES = set(card["makes_in_training"])
SYSTEMS = md2.SYSTEMS
COLD = card["variants"]["cold"]
OUT = {}
t0 = time.time()


def frame(df, cols, gap=None):
    X = df[cols].copy()
    if gap is not None and "gap_next" in X:
        X["gap_next"] = gap
    for c in ("fuel", "make_c"):
        if c in X:
            X[c] = pd.Categorical(X[c], categories=CATS[c])
    return X


boosters = {}
for s in SYSTEMS:
    b = xgb.Booster()
    b.load_model(str(ART / f"cold_{s}.json"))
    boosters[s] = b


def score(df, s, gap=None, contribs=False):
    dm = xgb.DMatrix(frame(df, COLD, gap), enable_categorical=True)
    return boosters[s].predict(dm, pred_contribs=contribs)


# ------------------------------------------------------------------ data
uk, _ = md2.uk_pairs()
nl, _ = md2.nl_pairs()
for d in (uk, nl):
    d["make_c"] = d.make.where(d.make.isin(MAKES), "OTHER")
print(f"[{time.time()-t0:.0f}s] UK pairs {len(uk):,} | NL pairs {len(nl):,}", flush=True)

# ------------------------------------------------------------------ 1. how the displayed percentile is built (replicate for two real plates)
dec = card["same_age_score_deciles"]
levels = np.array(card["decile_levels"])
vehicles = {
    "Hyundai i20 2022 (plate 19202803: last test 2026-11-16, valid until 2027-11-20)": dict(age_year=4, gap_next=1.01, fuel="petrol", make_c="Hyundai"),
    "Hyundai i20 2022 (plate 11898603: last test 2026-10-19, valid until 2027-07-16)": dict(age_year=4, gap_next=0.74, fuel="petrol", make_c="Hyundai"),
    "Nissan Micra 2014 (plate 9413531: last test 2026-11-12, valid until 2027-10-29)": dict(age_year=12, gap_next=0.96, fuel="petrol", make_c="Nissan"),
    "Nissan Micra 2014 (plate 9538331: last test 2026-01-14, valid until 2026-12-08)": dict(age_year=12, gap_next=0.90, fuel="petrol", make_c="Nissan"),
}
V = pd.DataFrame(list(vehicles.values()), index=list(vehicles.keys()))
audit_rows = []
for s in SYSTEMS:
    p = score(V, s)
    for (name, row), pi in zip(V.iterrows(), p):
        q = dec[f"cold/{s}"][str(int(row.age_year))]
        pct = float(np.interp(pi, q, levels, left=0.05, right=0.95)) * 100
        audit_rows.append({"vehicle": name, "system": s, "raw_probability": float(pi), "same_age_percentile_replicated": round(pct), "same_age_deciles_p": [round(x, 4) for x in q]})
OUT["replication_of_displayed_numbers"] = audit_rows

# ------------------------------------------------------------------ 2. calibration: the exported boosters ARE the probabilities (binary:logistic, no post-processing)
cfg = json.loads(boosters["brakes"].save_config())
OUT["objective"] = cfg["learner"]["objective"]["name"] if "objective" in cfg["learner"] else None

# ------------------------------------------------------------------ 3. what drives the scores: gain importance and per-vehicle contributions
imp = {}
for s in SYSTEMS:
    g = boosters[s].get_score(importance_type="total_gain")
    tot = sum(g.values())
    imp[s] = {k: round(v / tot, 3) for k, v in sorted(g.items(), key=lambda kv: -kv[1])}
OUT["gain_importance_cold"] = imp
contrib = {}
for s in SYSTEMS:
    c = score(V, s, contribs=True)
    contrib[s] = {name: dict(zip(COLD + ["bias"], [round(float(x), 3) for x in row])) for name, row in zip(V.index, c)}
OUT["log_odds_contributions_cold"] = contrib

# ------------------------------------------------------------------ 4. effect of the planned interval (gap_next): ranking value and size of the shift
gap_rows = []
nl_eval = nl[nl.target_date >= pd.Timestamp("2026-01-01")]
for s in SYSTEMS:
    y = nl_eval["next_" + s].to_numpy()
    p_real = score(nl_eval, s)
    p_one = score(nl_eval, s, gap=1.0)
    gap_rows.append({"system": s, "NL AUC with realised gap": float(roc_auc_score(y, p_real)), "NL AUC with gap fixed at 1.0": float(roc_auc_score(y, p_one)),
                     "mean |relative change| of p when gap fixed at 1": float(np.mean(np.abs(p_real / p_one - 1)))})
base = V.iloc[[0]].copy()
sens = {}
for s in SYSTEMS:
    sens[s] = {str(g): float(score(base.assign(gap_next=g), s)[0]) for g in (0.6, 0.74, 0.85, 1.0, 1.07, 1.3)}
OUT["gap_effect"] = {"external_validation": gap_rows, "i20_2022_probability_by_gap": sens}
print(f"[{time.time()-t0:.0f}s] gap effect done", flush=True)

# ------------------------------------------------------------------ 5. cross-fitted UK scores (cold, gap fixed at 1.0 at scoring time) = reference scores
params = {s: card["hyperparameters"][f"{s}/cold"] for s in SYSTEMS}
oof = {s: np.zeros(len(uk)) for s in SYSTEMS}
for s in SYSTEMS:
    for tri, vai in GroupKFold(n_splits=3).split(uk, groups=uk.unit):
        m = xgb.XGBClassifier(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist", enable_categorical=True, n_jobs=8, random_state=0, eval_metric="logloss", **params[s])
        m.fit(frame(uk.iloc[tri], COLD), uk.iloc[tri]["next_" + s])
        oof[s][vai] = m.predict_proba(frame(uk.iloc[vai], COLD, gap=1.0))[:, 1]
    print(f"[{time.time()-t0:.0f}s] cross-fit {s} done", flush=True)
nl_p = {s: score(nl, s, gap=1.0) for s in SYSTEMS}          # NL scored by the UK-trained exported models (out of sample)

# ------------------------------------------------------------------ 6. Israeli fleet (registry sample): scores only, no labels
il_raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
il_raw = il_raw[il_raw.sug_degem == "P"].copy()
il = normalise_registry(il_raw, reference_year=2026)
il["last"] = pd.to_datetime(il_raw["mivchan_acharon_dt"].to_numpy(), errors="coerce")
il["first_year"] = pd.to_numeric(pd.Series(il_raw["moed_aliya_lakvish"].astype(str).str.split("-").str[0].to_numpy()), errors="coerce")
il["age_year"] = (il["last"].dt.year - il["first_year"]).astype("float")
il["fuel"] = il.fuel.replace({"lpg_cng": "lpg_cng"})
il["make_c"] = il.make.str.title().replace({"Vauxhall": "Opel"})
il["make_c"] = il.make_c.where(il.make_c.isin(MAKES), "OTHER")
cov = il[il.fuel.isin(card["coverage"]["fuels"]) & il.age_year.between(*card["coverage"]["age_years_at_last_inspection"])].copy()
cov["gap_next"] = 1.0
OUT["israeli_fleet"] = {"passenger_sample": int(len(il)), "covered_by_model2": int(len(cov)), "share_covered": float(len(cov) / len(il)), "age_year_mean_covered": float(cov.age_year.mean()),
                        "uk_age_year_mean": float(uk.age_year.mean()), "nl_age_year_mean": float(nl.age_year.mean())}
il_p = {s: score(cov, s, gap=1.0) for s in SYSTEMS}

# ------------------------------------------------------------------ 7. compare reference populations and the two displayed scales
def pct_of(ref, x):
    ref = np.sort(ref)
    return float(np.searchsorted(ref, x, side="right") / len(ref) * 100)


p_v = {s: score(V, s, gap=1.0) for s in SYSTEMS}                      # the four example vehicles with gap standardised to 1.0
refs = {"UK cross-fitted (training population, all ages 3-20)": oof, "NL (independent validation population)": nl_p, "Israeli registry sample (covered vehicles, unlabelled)": il_p}
pooled = {s: np.r_[oof[s], nl_p[s]] for s in SYSTEMS}
refs["UK + NL pooled"] = pooled
table = []
for s in SYSTEMS:
    for rname, ref in refs.items():
        table.append({"system": s, "reference": rname, "mean_p": float(ref[s].mean()), "deciles_p": [round(float(x), 4) for x in np.quantile(ref[s], np.arange(0.1, 1.0, 0.1))],
                      "example_percentiles": {n.split(" (")[0] + f" #{i % 2 + 1}": round(pct_of(ref[s], p_v[s][i])) for i, n in enumerate(V.index)}})
OUT["reference_population_comparison"] = table
OUT["p_gap_fixed_examples"] = {s: [round(float(x), 4) for x in p_v[s]] for s in SYSTEMS}

# ------------------------------------------------------------------ 8. is a population-wide scale more useful than a same-age scale? (labels available in UK and NL)
def deciles_by_age(ref_p, ref_age, q=(0.2, 0.8)):
    d = pd.DataFrame({"a": ref_age, "p": ref_p}).groupby("a").p.quantile(list(q)).unstack()
    return d


use_rows = []
for s in SYSTEMS:
    for name, d, p in (("UK cross-fitted", uk, oof[s]), ("NL (UK-trained)", nl, nl_p[s])):
        y = d["next_" + s].to_numpy()
        age = d.age_year.to_numpy()
        thr_all = np.quantile(p, 0.8)
        top_all = p >= thr_all
        q = deciles_by_age(p, age)
        top_age = p >= pd.Series(age).map(q[0.8]).to_numpy()
        use_rows.append({"system": s, "data": name, "overall top-20% (all ages): share of defects captured": float(y[top_all].sum() / y.sum()), "overall top-20%: defect rate": float(y[top_all].mean()),
                         "same-age top-20%: share of defects captured": float(y[top_age].sum() / y.sum()), "same-age top-20%: defect rate": float(y[top_age].mean()), "base rate": float(y.mean()),
                         "Spearman(score shown, raw p): all-age percentile": float(spearmanr(pd.Series(p).rank(pct=True), p)[0]),
                         "Spearman(score shown, raw p): same-age percentile": float(spearmanr(pd.Series(p).groupby(age).rank(pct=True), p)[0])})
OUT["utility_of_scales"] = use_rows

# observed defect rate by general quintile (reference = the data itself) and by age group
band_rows = []
for s in SYSTEMS:
    for name, d, p in (("UK cross-fitted", uk, oof[s]), ("NL (UK-trained)", nl, nl_p[s])):
        ref = oof[s]                                              # one common reference (UK cross-fitted) for both countries
        cuts = np.quantile(ref, [0.2, 0.4, 0.6, 0.8])
        lvl = np.searchsorted(cuts, p)
        y = d["next_" + s].to_numpy()
        band_rows.append({"system": s, "data": name, "rate_by_level_1_to_5": [round(float(y[lvl == k].mean()), 4) for k in range(5)], "share_of_vehicles": [round(float((lvl == k).mean()), 3) for k in range(5)],
                          "mean_age_by_level": [round(float(d.age_year.to_numpy()[lvl == k].mean()), 1) for k in range(5)]})
OUT["observed_rate_by_common_level"] = band_rows

# ------------------------------------------------------------------ 9. coherence across ages (grid) and reliability
grid = []
for make, fuel in (("Toyota", "petrol"), ("Hyundai", "petrol"), ("Nissan", "petrol"), ("Kia", "diesel"), ("Skoda", "diesel"), ("Mazda", "petrol"), ("Toyota", "hybrid")):
    G = pd.DataFrame({"age_year": list(range(3, 21)), "gap_next": 1.0, "fuel": fuel, "make_c": make})
    for s in SYSTEMS:
        p = score(G, s)
        grid.append({"make": make, "fuel": fuel, "system": s, "p_by_age_3_to_20": [round(float(x), 4) for x in p], "non_monotone_steps": int((np.diff(p) < -1e-6).sum())})
OUT["coherence_grid"] = grid
obs_by_age = {s: {str(a): round(float(uk.loc[uk.age_year == a, "next_" + s].mean()), 4) for a in range(3, 21)} for s in SYSTEMS}
OUT["observed_rate_by_age_uk"] = obs_by_age
rel = []
for s in SYSTEMS:
    for name, d, p in (("UK cross-fitted", uk, oof[s]), ("NL (UK-trained)", nl, nl_p[s])):
        y = d["next_" + s].to_numpy()
        q = pd.qcut(p, 10, duplicates="drop")
        t = pd.DataFrame({"y": y, "p": p}).groupby(q, observed=True).agg(p=("p", "mean"), y=("y", "mean"))
        rel.append({"system": s, "data": name, "mean_predicted_by_decile": [round(float(x), 4) for x in t.p], "observed_by_decile": [round(float(x), 4) for x in t.y]})
OUT["reliability_cold_gap1"] = rel
(ROOT / "ml" / "audit_risk_scale_results.json").write_text(json.dumps(OUT, indent=1), encoding="utf-8")
print(f"[{time.time()-t0:.0f}s] written ml/audit_risk_scale_results.json", flush=True)

# ------------------------------------------------------------------ 10. proposed scales for the two example vehicles (gap standardised to 12 months; UK cross-fitted reference)
ex = []
for i, (name, row) in enumerate(V.iterrows()):
    for s in SYSTEMS:
        p = float(p_v[s][i])
        same_age = oof[s][uk.age_year.to_numpy() == int(row.age_year)]
        ex.append({"vehicle": name, "system": s, "raw_probability_gap12m": round(p, 4), "general_percentile_UK_reference": round(pct_of(oof[s], p)), "relative_to_reference_mean": round(p / float(oof[s].mean()), 2),
                   "same_age_percentile_gap12m": round(pct_of(same_age, p)), "age_year": int(row.age_year), "reference_mean_p": round(float(oof[s].mean()), 4)})
OUT["proposed_scale_examples"] = ex
cuts = {s: [round(float(x), 4) for x in np.quantile(oof[s], [0.2, 0.4, 0.6, 0.8])] for s in SYSTEMS}
OUT["proposed_level_cut_points_p"] = cuts
(ROOT / "ml" / "audit_risk_scale_results.json").write_text(json.dumps(OUT, indent=1), encoding="utf-8")
print(f"[{time.time()-t0:.0f}s] proposed examples written", flush=True)
