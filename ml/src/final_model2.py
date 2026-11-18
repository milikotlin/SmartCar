"""FINAL training, validation and export of Model 2 (risk that the NEXT annual inspection finds a defect, by system).

Approved design:
  * XGBoost classifier per system (brakes, electrical, engine-related), natural objective (probabilities stay probabilities);
  * primary data: UK MOT (vehicle-level sample, test in 2022 -> next test in 2023, with the measured odometer);
  * independent validation: Dutch RDW (consecutive periodic inspections of the same plates; no odometer);
  * variants: cold (registry only), hist (+ results of the previous inspection), and the same two with a MEASURED odometer
    (cold_odo, hist_odo). The mileage estimated by Model 1 is NOT a feature (it did not improve any metric in notebooks 07-09);
  * features available in the real system only: age, planned interval to the next inspection, fuel, make, previous inspection result, measured odometer.

Exports (backend/app/ml/artifacts/model2/): <variant>_<system>.json boosters + model2_card.json (features, categories, thresholds, metrics, limits).
Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model2.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_recall_curve, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model2_data as md2  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "backend" / "app" / "ml" / "artifacts" / "model2"
SYSTEMS = md2.SYSTEMS
FUELS = md2.FUELS
HIST = ["cur_brakes", "cur_electrical", "cur_engine_emissions", "cur_any_defect"]
COLD = ["age_year", "gap_next", "fuel", "make_c"]
VARIANTS = {"cold": COLD, "cold_odo": COLD + ["km"], "hist": COLD + HIST, "hist_odo": COLD + HIST + ["km"]}
GRID = [{"max_depth": 3, "n_estimators": 200, "min_child_weight": 50}, {"max_depth": 4, "n_estimators": 300, "min_child_weight": 100},
        {"max_depth": 5, "n_estimators": 300, "min_child_weight": 100}, {"max_depth": 6, "n_estimators": 400, "min_child_weight": 100}]
SEED = 0


def ece(y, p, bins=10):
    q = pd.qcut(p, bins, duplicates="drop")
    t = pd.DataFrame({"y": y, "p": p}).groupby(q, observed=True).agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
    return float((abs(t.p - t.y) * t.n).sum() / t.n.sum())


def capture(y, p, frac=0.2):
    k = int(len(p) * frac)
    idx = np.argsort(-p)[:k]
    y = np.asarray(y)
    return float(y[idx].sum() / y.sum())


def best_f1_thr(y, p):
    pr, rc, th = precision_recall_curve(y, p)
    f1 = 2 * pr * rc / np.clip(pr + rc, 1e-12, None)
    return float(th[int(np.nanargmax(f1[:-1]))])


def shift_to_rate(p, rate):
    from scipy.optimize import brentq
    lg = np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
    f = lambda dl: (1 / (1 + np.exp(-(lg + dl)))).mean() - rate
    return 1 / (1 + np.exp(-(lg + brentq(f, -6, 6))))


def prep(df, cols, cats):
    X = df[cols].copy()
    for c in cols:
        if c in cats:
            X[c] = pd.Categorical(X[c], categories=cats[c])
    return X


def make_model(params):
    return xgb.XGBClassifier(learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist", enable_categorical=True, n_jobs=8, random_state=SEED,
                             eval_metric="logloss", **params)


def metrics_row(y, p, thr=None):
    row = {"n": int(len(y)), "prevalence": float(np.mean(y)), "ROC-AUC": float(roc_auc_score(y, p)), "PR-AUC": float(average_precision_score(y, p)), "capture_top20": capture(y, p),
           "ECE": ece(y, p), "Brier": float(brier_score_loss(y, p)), "mean_predicted": float(np.mean(p))}
    if thr is not None:
        pred = p >= thr
        tp = int((pred & (np.asarray(y) == 1)).sum())
        row.update({"threshold": thr, "flagged": float(pred.mean()), "Precision": tp / max(int(pred.sum()), 1), "Recall": tp / int(np.sum(y)), "F1": float(f1_score(y, pred))})
    return row


def lr_pipe(cols):
    num = [c for c in cols if c not in ("fuel", "make_c", "age_year")]
    return Pipeline([("p", ColumnTransformer([("a", SplineTransformer(n_knots=6, degree=3), ["age_year"]), ("n", StandardScaler(), num),
                                              ("c", OneHotEncoder(handle_unknown="ignore", min_frequency=50, sparse_output=False), ["fuel", "make_c"])])), ("m", LogisticRegression(max_iter=2000))])


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    uk, uk_info = md2.uk_pairs()
    nl, nl_info = md2.nl_pairs()
    print("UK pairs", uk_info, "| NL pairs", nl_info, flush=True)
    top = uk.make.value_counts().head(60).index.tolist()
    MAKES = sorted(top)
    for d in (uk, nl):
        d["make_c"] = d.make.where(d.make.isin(MAKES), "OTHER")
    CATS = {"fuel": FUELS, "make_c": MAKES + ["OTHER"]}
    print(f"UK prevalence of the target: { {s: round(float(uk['next_' + s].mean()), 4) for s in SYSTEMS} } | share of NL cars with a make outside the UK list: {(nl.make_c == 'OTHER').mean():.3f}", flush=True)

    # ---------------- development split on the UK: vehicles disjoint AND later targets for the test part
    veh = np.array(uk.unit.drop_duplicates().tolist())            # np.array(...) copy: a view would let shuffle scramble the table (bug found in notebook 09)
    rng = np.random.default_rng(SEED)
    rng.shuffle(veh)
    n = len(veh)
    trv, vav, tev = set(veh[:int(.7 * n)]), set(veh[int(.7 * n):int(.85 * n)]), set(veh[int(.85 * n):])
    tmid = uk.target_date.quantile(0.6)
    tr = uk[uk.unit.isin(trv) & (uk.target_date <= tmid)]
    va = uk[uk.unit.isin(vav) & (uk.target_date <= tmid)]
    te = uk[uk.unit.isin(tev) & (uk.target_date > tmid)]
    assert not (set(tr.unit) & set(te.unit)) and not (set(va.unit) & set(te.unit)) and tr.target_date.max() <= tmid < te.target_date.min()
    print(f"UK development split: train {len(tr):,} | validation {len(va):,} | test {len(te):,} pairs (test targets after {tmid.date()}, unseen vehicles)", flush=True)

    # ---------------- hyper-parameter selection on validation (log-loss), cold and hist; odometer variants reuse them
    best = {}
    tuning = []
    for s in SYSTEMS:
        t = "next_" + s
        for v in ("cold", "hist"):
            scores = []
            for g in GRID:
                m = make_model(g).fit(prep(tr, VARIANTS[v], CATS), tr[t])
                p = m.predict_proba(prep(va, VARIANTS[v], CATS))[:, 1]
                scores.append((float(-np.mean(va[t] * np.log(np.clip(p, 1e-9, 1)) + (1 - va[t]) * np.log(np.clip(1 - p, 1e-9, 1)))), float(roc_auc_score(va[t], p)), g))
            ll, auc, g = min(scores, key=lambda r: r[0])
            best[(s, v)] = g
            tuning.append({"system": s, "variant": v, "chosen": g, "validation_logloss": ll, "validation_auc": auc})
            print(f"  tuning {s}/{v}: {g} logloss {ll:.4f} AUC {auc:.4f}", flush=True)
        best[(s, "cold_odo")] = best[(s, "cold")]
        best[(s, "hist_odo")] = best[(s, "hist")]

    # ---------------- UK test metrics (all variants) + Logistic Regression benchmark
    uk_test, lr_bench = [], []
    for s in SYSTEMS:
        t = "next_" + s
        for v, cols in VARIANTS.items():
            m = make_model(best[(s, v)]).fit(prep(tr, cols, CATS), tr[t])
            pv, pt = m.predict_proba(prep(va, cols, CATS))[:, 1], m.predict_proba(prep(te, cols, CATS))[:, 1]
            r = metrics_row(te[t].to_numpy(), pt, best_f1_thr(va[t], pv))
            r.update({"system": s, "variant": v})
            uk_test.append(r)
            if v in ("cold", "hist"):
                lr_cols = [c for c in cols]
                lr = lr_pipe(lr_cols).fit(tr[lr_cols].astype({"fuel": str, "make_c": str}), tr[t])
                pl = lr.predict_proba(te[lr_cols].astype({"fuel": str, "make_c": str}))[:, 1]
                lr_bench.append({"system": s, "variant": v, **metrics_row(te[t].to_numpy(), pl)})
        print(f"  UK test {s}: " + ", ".join(f"{r['variant']} AUC {r['ROC-AUC']:.3f}" for r in uk_test if r["system"] == s), flush=True)
    base_rate = {s: float(uk["next_" + s].mean()) for s in SYSTEMS}

    # ---------------- external validation on the Dutch RDW (models trained on ALL UK pairs; NL targets from 2026 on)
    nl_test = nl[nl.target_date >= pd.Timestamp("2026-01-01")]
    ext, nl_inc = [], []
    for s in SYSTEMS:
        t = "next_" + s
        for v in ("cold", "hist"):
            m = make_model(best[(s, v)]).fit(prep(uk, VARIANTS[v], CATS), uk[t])
            p = m.predict_proba(prep(nl_test, VARIANTS[v], CATS))[:, 1]
            y = nl_test[t].to_numpy()
            r = metrics_row(y, p)
            r["ECE_after_base_rate_correction"] = ece(y, shift_to_rate(p, y.mean()))
            r.update({"system": s, "variant": v, "trained_on": "UK", "tested_on": "NL (targets 2026)"})
            ext.append(r)
            # reference: the same configuration trained in-country on NL (training targets before 2026)
            mn = make_model(best[(s, v)]).fit(prep(nl[nl.target_date < pd.Timestamp("2026-01-01")], VARIANTS[v], CATS), nl[nl.target_date < pd.Timestamp("2026-01-01")][t])
            pn = mn.predict_proba(prep(nl_test, VARIANTS[v], CATS))[:, 1]
            nl_inc.append({"system": s, "variant": v, **metrics_row(y, pn)})
        print(f"  NL external {s}: " + ", ".join(f"{r['variant']} AUC {r['ROC-AUC']:.3f} (in-country {[q['ROC-AUC'] for q in nl_inc if q['system']==s and q['variant']==r['variant']][0]:.3f})" for r in ext if r["system"] == s), flush=True)

    # ---------------- cross-fitted scores on ALL UK pairs: same-age reference thresholds and calibration check
    gkf = GroupKFold(n_splits=3)
    thresholds, ref_rates, oof_cal = {}, {}, []
    ages = sorted(uk.age_year.unique().tolist())
    for s in SYSTEMS:
        t = "next_" + s
        ref_rates[s] = {str(a): float(uk.loc[uk.age_year == a, t].mean()) for a in ages}
        for v, cols in VARIANTS.items():
            oof = np.zeros(len(uk))
            for tri, vai in gkf.split(uk, groups=uk.unit):
                m = make_model(best[(s, v)]).fit(prep(uk.iloc[tri], cols, CATS), uk.iloc[tri][t])
                oof[vai] = m.predict_proba(prep(uk.iloc[vai], cols, CATS))[:, 1]
            oof_cal.append({"system": s, "variant": v, "ECE": ece(uk[t].to_numpy(), oof), "ROC-AUC": float(roc_auc_score(uk[t], oof))})
            levels = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            q = pd.DataFrame({"a": uk.age_year.to_numpy(), "p": oof}).groupby("a").p.quantile(levels).unstack()
            thresholds[f"{v}/{s}"] = {str(a): [float(x) for x in q.loc[a, levels]] for a in q.index}    # deciles of the cross-fitted score within each age
            # share of the defects found by the 20% of vehicles ranked highest WITHIN their age (what the "higher" band means)
            hi = oof >= uk.age_year.map({a: q.loc[a, 0.8] for a in q.index}).to_numpy()
            oof_cal[-1].update({"share_flagged_higher_band": float(hi.mean()), "share_of_defects_in_higher_band": float(uk[t].to_numpy()[hi].sum() / uk[t].sum()),
                                "defect_rate_in_higher_band": float(uk[t].to_numpy()[hi].mean())})
        print(f"  cross-fitted {s} done", flush=True)

    # ---------------- final models on ALL UK pairs -> export
    for s in SYSTEMS:
        for v, cols in VARIANTS.items():
            m = make_model(best[(s, v)]).fit(prep(uk, cols, CATS), uk["next_" + s])
            m.get_booster().save_model(OUT / f"{v}_{s}.json")
    card = {
        "name": "Model 2 - risk that the next annual inspection finds a defect, by system", "version": "1.0.0", "trained_at": time.strftime("%Y-%m-%d"),
        "target": "defect found at the NEXT annual inspection (about 12 months ahead) of the same vehicle, by system; NOT a breakdown and NOT a failure forecast",
        "systems": {"brakes": "brake components, fluid, braking performance", "electrical": "lighting and signalling, battery, wiring (mostly lamps)", "engine_emissions": "exhaust emissions, fuel system, mounts, leaks (not engine health)"},
        "variants": {k: v for k, v in VARIANTS.items()}, "categories": CATS, "makes_in_training": MAKES,
        "coverage": {"fuels": FUELS, "age_years_at_last_inspection": list(md2.AGE_RANGE), "makes": "makes outside the list are mapped to OTHER (lower evidence)"},
        "training_data": {"primary": "UK DVSA MOT (OGL v3.0), 1-in-41 vehicle sample, test in 2022 -> next test in 2023", "uk": uk_info, "validation": "Dutch RDW open data (public domain)", "nl": nl_info,
                          "uk_base_rate_next_inspection": base_rate, "mileage_estimated_by_model1": "not used: no gain in any experiment (notebooks 07, 09)"},
        "hyperparameters": {f"{s}/{v}": best[(s, v)] for s in SYSTEMS for v in VARIANTS}, "tuning": tuning,
        "uk_development_split": {"train": int(len(tr)), "validation": int(len(va)), "test": int(len(te)), "test_targets_after": str(tmid.date())},
        "uk_test_metrics": uk_test, "uk_logistic_regression_benchmark": lr_bench, "netherlands_external_validation": ext, "netherlands_in_country_reference": nl_inc,
        "uk_cross_fitted": oof_cal, "same_age_score_deciles": thresholds, "decile_levels": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], "reference_rate_by_age": ref_rates,
        "bands": {"higher": "score above the 80th percentile of vehicles of the same age (cross-fitted UK scores)", "lower": "below the 20th percentile", "typical": "otherwise"},
        "limitations": ["foreign (UK/NL) vehicles and inspections: not validated on Israeli vehicles", "target is an inspection defect found about a year later, not a breakdown",
                        "absolute probabilities are calibrated to UK base rates and shift between countries (e.g. electrical 11% UK against 18% NL): shown as relative risk",
                        "history variants need the previous INSPECTION result; maintenance records are not equivalent and are not used as such",
                        "XGBoost and Logistic Regression perform equally within the noise of the splits", "discrimination is modest: a risk ranking, not a diagnosis"],
        "library_versions": {"xgboost": xgb.__version__, "numpy": np.__version__, "pandas": pd.__version__},
    }
    (OUT / "model2_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(f"exported to {OUT} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
