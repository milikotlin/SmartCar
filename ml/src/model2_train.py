"""FINAL training of Model 2 (Smart_Car_Models.pdf) with data augmentation. Supersedes ml/archive/spec_model2.py.

Training data : combustion = Kaggle Dataset 1 (two original files, leak-free columns) enriched with the Dataset 4 failure distribution + SYNTHETIC vehicles generated from the FIT part of the real
                UK inspections; electric / hybrid = Kaggle Dataset 5 + the electric (Tesla) rows of Dataset 1 + SYNTHETIC vehicles generated from the electric / hybrid FIT inspections.
Never used    : Maintenance_Type and Maintenance_Cost (they encode the label), every sensor column, Anomalies_Detected, Predictive_Score.
Judged on     : REAL outcomes only - UK val (every choice), UK test and the whole Netherlands (opened once, at the end). Metrics: ROC-AUC, Recall and Precision when the 40% of vehicles with the
                highest score are flagged (a fixed share, so Recall cannot be bought by flagging everything).
Experiments   : 1 training data (ablation), 2 class imbalance (none / scale_pos_weight / SMOTE) and Logistic Regression baselines, 3 hyper-parameters that maximise Recall on the real val vehicles.

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/model2_train.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m2_lab import *  # noqa: E402,F403
from imblearn.over_sampling import SMOTE  # noqa: E402
from imblearn.pipeline import Pipeline as ImbPipeline  # noqa: E402
from kaggle_sources import SOURCE  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

PREV = Path.home() / "smartcar_data" / "interim" / "previous_spec"
N_SYNTH = {"ice": 200_000, "ev": 60_000}
BRANCH_FUELS = {"ice": ["petrol", "diesel", "lpg_cng"], "ev": ["hybrid", "electric"]}
SYS_FEATURES = {"ice": M2_FEATURES, "ev": M2_EV_FEATURES}
MONO = {"vehicle_age": 1, "km": 1, "days_since_last_maintenance": 1, "failure_history": 1, "brand_reliability_index": -1, "last_service_distance": 1,
        "d4_engine_fault_rate": 1, "d4_brake_fault_rate": 1, "d4_battery_fault_rate": 1}
GRID = [dict(), dict(max_depth=4, min_child_weight=100), dict(max_depth=6, min_child_weight=100), dict(max_depth=7, min_child_weight=200, reg_lambda=20), dict(max_depth=3, n_estimators=600),
        dict(max_depth=5, n_estimators=800, learning_rate=0.025, min_child_weight=150), dict(max_depth=4, n_estimators=1000, learning_rate=0.03, min_child_weight=300, reg_lambda=20),
        dict(max_depth=5, min_child_weight=200, colsample_bytree=0.6, reg_lambda=20)]
t0 = time.time()
log = lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True)


# ------------------------------------------------------------------ training tables (masked: "unknown" must not look like "zero")
def official_rows(d, bri, d4, days_pool, seed=0):
    """Half of the rows see the true odometer (km_measured=1), half Model 1's estimate; half see the last inspection result. Inspections do not record services: the days are drawn at random from
    Dataset 1 for half of the rows, so that merely KNOWING the days says nothing (only Dataset 1 says what their value means)."""
    r, n = np.random.default_rng(seed), len(d)
    meas = r.random(n) < 0.5
    days = np.where(r.random(n) < 0.5, r.choice(days_pool, n), np.nan)
    hist = np.where(r.random(n) < 0.5, d.any_defect, np.nan)
    return features(d.age_year, np.where(meas, d.km, d.km_model1), meas, days, hist, d.make.str.lower().map(bri["index"]).fillna(50.0), d4)


def kaggle_rows(d, d4, seed=0, mask=0.5):
    r, n = np.random.default_rng(seed), len(d)
    return features(d.age_year, d.km, np.zeros(n), np.where(r.random(n) < mask, np.nan, d.days), np.where(r.random(n) < mask, np.nan, d.fh), d.brand, d4)


def match_base_rate(d, n, base, seed=0):
    """`n` Dataset 1 rows, the same number from each file, with the real base rate: otherwise the file a row comes from (base rates 0.30 / 0.77) would leak into the score."""
    out = []
    for i, (_, g) in enumerate(d.groupby("file")):
        k = n // d.file.nunique()
        for lab, share in ((1, base), (0, 1 - base)):
            s = g[g.y == lab]
            out.append(s.sample(min(int(k * share), len(s)), random_state=seed + i))
    return pd.concat(out, ignore_index=True)


def d5_rows(d5, d4):
    n = len(d5)
    nan = np.full(n, np.nan)
    f = features(nan, np.zeros(n), np.zeros(n), nan, nan, nan, d4, **{c: d5[c].to_numpy(float) for c in M2_EV_EXTRA})
    f[["km", "d4_engine_fault_rate", "d4_brake_fault_rate", "d4_battery_fault_rate"]] = np.nan
    return f


# ------------------------------------------------------------------ models
def xgb(cols, **kw):
    base = dict(n_estimators=400, learning_rate=0.05, max_depth=5, min_child_weight=50, subsample=0.8, colsample_bytree=0.8, reg_lambda=5, tree_method="hist", n_jobs=8, random_state=SEED,
                monotone_constraints=tuple(MONO.get(c, 0) for c in cols))
    base.update(kw)
    return XGBClassifier(**base)


def build(kind, cols, spw, **kw):
    if kind == "XGBoost (no correction)":
        return Pipeline([("model", xgb(cols, **kw))])
    if kind == "XGBoost + scale_pos_weight":
        return Pipeline([("model", xgb(cols, scale_pos_weight=spw, **kw))])
    if kind == "XGBoost + SMOTE":                                             # SMOTE needs complete rows: median imputation
        return ImbPipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("smote", SMOTE(random_state=SEED)), ("model", xgb(cols, **kw))])
    imp = SimpleImputer(strategy="median", add_indicator=True)
    if kind == "Logistic Regression (balanced)":
        return Pipeline([("impute", imp), ("scale", StandardScaler()), ("model", LogisticRegression(max_iter=3000, class_weight="balanced"))])
    return ImbPipeline([("impute", imp), ("scale", StandardScaler()), ("smote", SMOTE(random_state=SEED)), ("model", LogisticRegression(max_iter=3000))])


def real_scores(m, d, bri, d4, cols):
    return {sc: m.predict_proba(scenario(d, bri, d4, o, h)[cols])[:, 1] for sc, (o, h) in SCENARIOS.items()}


def summary(d, scores):
    r = {sc: judge(d.y, p) for sc, p in scores.items()}
    r["mean"] = {k: float(np.mean([r[s][k] for s in SCENARIOS])) for k in ("roc_auc", "pr_auc", "recall", "precision")}
    return r


def show(branch, name, r):
    log(f"[{branch}] {name:50s} mean AUC {r['mean']['roc_auc']:.4f} recall {r['mean']['recall']:.4f} precision {r['mean']['precision']:.4f} | " + " ".join(f"{r[s]['roc_auc']:.3f}" for s in SCENARIOS))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def platt(y, p):
    m = LogisticRegression(C=1e6).fit(logit(p).reshape(-1, 1), y)
    return float(m.coef_[0, 0]), float(m.intercept_[0])


def apply_platt(p, ab):
    return 1 / (1 + np.exp(-(ab[0] * logit(p) + ab[1])))


def reliability(y, p, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    rows = [{"predicted": float(p[b == i].mean()), "observed": float(y[b == i].mean()), "n": int((b == i).sum())} for i in range(bins) if (b == i).any()]
    return rows, float(sum(abs(r["predicted"] - r["observed"]) * r["n"] for r in rows) / len(p))


# ------------------------------------------------------------------ one branch
def train_branch(branch, fit, val, test, nl, kag_train, kag_test, d5, bri, d4, days_pool, R):
    cols, base, N = SYS_FEATURES[branch], float(fit.y.mean()), N_SYNTH[branch]
    so = synth_official(fit, N, seed=7)
    so["km_model1"] = model1_km(so)
    R["synthetic_rows"] = len(so)
    R["synthetic_fidelity (against real vehicles the generator never saw)"] = fidelity(val, so, ["age_year", "cc", "km"], ["fuel", "any_defect", "y"])
    S = (official_rows(so, bri, d4, days_pool), so.y.to_numpy())
    real = fit.sample(min(len(fit), N), random_state=1)
    real = real.assign(km_model1=model1_km(real))
    RO = (official_rows(real, bri, d4, days_pool), real.y.to_numpy())
    log(f"[{branch}] fit {len(fit):,} val {len(val):,} test {len(test):,} NL {len(nl):,}; synthetic {len(so):,}; base rate {base:.3f}; fidelity {R['synthetic_fidelity (against real vehicles the generator never saw)']['ks_statistic']}")

    def kaggle_part(n):
        k = match_base_rate(kag_train, n if branch == "ice" else n // 2, base)
        parts = [(kaggle_rows(k, d4), k.y.to_numpy())]
        if branch == "ev":                                                    # Dataset 5 with its own labels, resampled to the requested size
            e = d5.sample(n - n // 2, replace=True, random_state=0)
            parts.append((d5_rows(e, d4), e.y.to_numpy()))
        return parts

    def stack(parts):
        return pd.concat([p[0] for p in parts], ignore_index=True)[cols], np.concatenate([p[1] for p in parts])

    def run(kind, parts, **kw):
        X, y = stack(parts)
        m = build(kind, cols, float((y == 0).sum() / (y == 1).sum()), **kw).fit(X, y)
        return m, summary(val, real_scores(m, val, bri, d4, cols))

    age_rate = fit.groupby("age_year").y.mean()
    R["age_only_val"] = judge(val.y, val.age_year.map(age_rate).fillna(base))
    log(f"[{branch}] age only: {R['age_only_val']}")

    # 1. training data
    R["experiment_1_training_data"] = {}
    for name, parts in {"Kaggle only (no augmentation)": kaggle_part(min(N, 60_000)), "Synthetic official only": [S], "Kaggle 5% + synthetic official": kaggle_part(int(N * 0.05)) + [S],
                        "Kaggle 10% + synthetic official": kaggle_part(int(N * 0.10)) + [S], "Kaggle 20% + synthetic official": kaggle_part(int(N * 0.20)) + [S],
                        "Kaggle 40% + synthetic official": kaggle_part(int(N * 0.40)) + [S], "Kaggle 10% + REAL official rows (reference, not used)": kaggle_part(int(N * 0.10)) + [RO]}.items():
        _, r = run("XGBoost (no correction)", parts)
        R["experiment_1_training_data"][name] = r
        show(branch, name, r)
    e1 = R["experiment_1_training_data"]
    top = e1["Synthetic official only"]["mean"]["roc_auc"]
    ok = [s for s in (40, 20, 10, 5) if e1[f"Kaggle {s}% + synthetic official"]["mean"]["roc_auc"] >= top - 0.003]
    share = (ok[0] if ok else 5) / 100
    R["experiment_1_chosen"] = {"kaggle_share": share, "rule": "the largest Kaggle share whose mean ROC-AUC on the real validation vehicles is within 0.003 of no Kaggle rows at all"}
    log(f"[{branch}] Kaggle share chosen: {share}")
    parts = kaggle_part(int(N * share)) + [S]

    # 2. imbalance and algorithm
    R["experiment_2_imbalance"] = {}
    for kind in ("XGBoost (no correction)", "XGBoost + scale_pos_weight", "XGBoost + SMOTE", "Logistic Regression (balanced)", "Logistic Regression + SMOTE"):
        _, r = run(kind, parts)
        R["experiment_2_imbalance"][kind] = r
        show(branch, kind, r)
    key = lambda r: (round(r["mean"]["recall"], 3), r["mean"]["roc_auc"])
    kind = max(("XGBoost + scale_pos_weight", "XGBoost + SMOTE", "Logistic Regression (balanced)", "Logistic Regression + SMOTE"), key=lambda k: key(R["experiment_2_imbalance"][k]))
    R["experiment_2_chosen"] = kind
    log(f"[{branch}] chosen: {kind}")

    # 3. tuning for Recall
    R["experiment_3_tuning"], best = [], None
    for kw in (GRID if kind.startswith("XGB") else [{}]):
        m, r = run(kind, parts, **kw)
        R["experiment_3_tuning"].append({"params": kw, **r})
        show(branch, json.dumps(kw)[:50], r)
        if best is None or key(r) > key(best[2]):
            best = (m, kw, r)
    m, kw, rv = best
    final = Pipeline([(n, s) for n, s in m.steps if n != "smote"])            # SMOTE acts only while training
    R["final"] = {"algorithm": kind, "params": kw, "val": rv}

    # probability calibration and level cuts on the real val vehicles (all four situations together)
    sv = real_scores(final, val, bri, d4, cols)
    pv, yv = np.concatenate(list(sv.values())), np.tile(val.y.to_numpy(), len(sv))
    ab = platt(yv, pv)
    cv = apply_platt(pv, ab)
    cuts = [float(np.quantile(cv, 1 / 3)), float(np.quantile(cv, 2 / 3))]
    R["overfitting_check"] = {"train_auc": float(roc_auc_score(S[1], final.predict_proba(S[0][cols])[:, 1])),
                              "val_auc_same_masking": float(roc_auc_score(val.y, final.predict_proba(official_rows(val, bri, d4, days_pool, 1)[cols])[:, 1])),
                              "real_fit_auc_same_masking": float(roc_auc_score(RO[1], final.predict_proba(RO[0][cols])[:, 1]))}

    # ---------------- FINAL TESTS, once
    prev, prev_card = joblib.load(PREV / f"model2_{branch}_pipeline.joblib"), json.loads((PREV / "model2_card.json").read_text(encoding="utf-8"))

    def previous(d, o, h):
        if branch == "ev":
            return prev.predict_proba(pd.DataFrame(np.full((len(d), 4), np.nan), columns=M2_EV_EXTRA))[:, 1]
        km = d.km if o else d.km_model1
        x = pd.DataFrame({"vehicle_age": d.age_year.astype(float), "km": km, "days_since_last_maintenance": np.nan, "failure_history": d.any_defect.astype(float) if h else 0.0,
                          "brand_reliability_index": d.make.str.lower().map(prev_card["brand_reliability_index"]["index"]).fillna(50.0), **d4_cols(km, d4), "maintenance_type": "Unknown"})
        return prev.predict_proba(x)[:, 1]

    R["test"] = {}
    for where, d in (("uk", test), ("nl", nl)):
        if len(d) < 500:
            continue
        R["test"][where] = {"vehicles": len(d), "base_rate": float(d.y.mean()), "scenarios": {}, "age_only": judge(d.y, d.age_year.map(age_rate).fillna(base))}
        for sc, (o, h) in SCENARIOS.items():
            if where == "nl" and o:                                          # the Dutch data have no odometer
                continue
            p = final.predict_proba(scenario(d, bri, d4, o, h)[cols])[:, 1]
            c = apply_platt(p, ab)
            lv = np.where(c <= cuts[0], 0, np.where(c <= cuts[1], 1, 2))
            rel, ece = reliability(d.y.to_numpy(), c)
            q = {"new": judge(d.y, p), "previous": judge(d.y, previous(d, o, h)), "within_age_auc": within_age_auc(d, p), "mean_calibration_error": ece, "reliability": rel,
                 "level_share": [float((lv == i).mean()) for i in range(3)], "level_rate": [float(d.y[lv == i].mean()) if (lv == i).any() else None for i in range(3)]}
            R["test"][where]["scenarios"][sc] = q
            log(f"[{branch}] TEST {where} {sc:26s} new {q['new']['roc_auc']:.3f} R {q['new']['recall']:.3f} P {q['new']['precision']:.3f} | previous {q['previous']['roc_auc']:.3f} R {q['previous']['recall']:.3f} "
                f"P {q['previous']['precision']:.3f} | age only {R['test'][where]['age_only']['roc_auc']:.3f} | within age {q['within_age_auc']:.3f} | ECE {ece:.3f} | level rates {[round(x, 2) if x is not None else None for x in q['level_rate']]}")
    sc0 = R["test"]["uk"]["scenarios"]
    R["test"]["uk"]["mean"] = {w: {k: float(np.mean([sc0[s][w][k] for s in sc0])) for k in ("roc_auc", "pr_auc", "recall", "precision")} for w in ("new", "previous")}
    # bootstrap interval of the gain over age only, plate-only situation (the hardest one)
    p = final.predict_proba(scenario(test, bri, d4, False, False)[cols])[:, 1]
    a, yt = test.age_year.map(age_rate).fillna(base).to_numpy(), test.y.to_numpy()
    rng, gains = np.random.default_rng(0), []
    for _ in range(200):
        i = rng.integers(0, len(yt), len(yt))
        gains.append(roc_auc_score(yt[i], p[i]) - roc_auc_score(yt[i], a[i]))
    R["test"]["gain_over_age_only_plate_only_95ci"] = [float(np.quantile(gains, 0.025)), float(np.mean(gains)), float(np.quantile(gains, 0.975))]
    if branch == "ice":                                                       # Dataset 1 rows never used for training (per file, with the columns the model is allowed to see)
        R["test"]["dataset1_held_out"] = {f: judge(g.y, final.predict_proba(kaggle_rows(g, d4, mask=0.0)[cols])[:, 1]) for f, g in kag_test.groupby("file")}
        log(f"[ice] Dataset 1 held out {R['test']['dataset1_held_out']}")
    else:
        R["test"]["dataset5"] = {"note": "the four columns left after the strict dropping carry no signal", "single_feature_auc": {c: float(roc_auc_score(d5.y, d5[c])) for c in M2_EV_EXTRA}}
    levels = {"cut_probabilities": cuts, "rule": "Low / Moderate / High = lowest, middle and highest third of real UK vehicles (validation part) by calibrated score",
              "test_rate_by_level": [float(np.nanmean([np.nan if sc0[s]["level_rate"][i] is None else sc0[s]["level_rate"][i] for s in sc0])) for i in range(3)],
              "test_share_by_level": [float(np.mean([sc0[s]["level_share"][i] for s in sc0])) for i in range(3)]}
    R["levels"], R["platt"] = levels, list(ab)
    joblib.dump(final, ART / f"model2_{branch}_pipeline.joblib", compress=3)
    log(f"[{branch}] over-fitting {R['overfitting_check']} | gain over age {R['test']['gain_over_age_only_plate_only_95ci']} | levels {levels}")
    nl_s = R["test"].get("nl", {})
    return {"chosen": kind, "params": kw, "kaggle_share": share, "synthetic_rows": len(so), "test": {**R["test"]["uk"]["mean"]["new"], "base_rate": R["test"]["uk"]["base_rate"], "vehicles": len(test)},
            "previous_on_same_test": R["test"]["uk"]["mean"]["previous"], "age_only_auc": R["test"]["uk"]["age_only"]["roc_auc"], "by_scenario": {s: v["new"] for s, v in sc0.items()},
            "previous_by_scenario": {s: v["previous"] for s, v in sc0.items()}, "netherlands": {s: v["new"] for s, v in nl_s.get("scenarios", {}).items()},
            "netherlands_previous": {s: v["previous"] for s, v in nl_s.get("scenarios", {}).items()}, "netherlands_age_only_auc": nl_s.get("age_only", {}).get("roc_auc"),
            "levels": levels, "platt": list(ab), "mean_calibration_error": float(np.mean([v["mean_calibration_error"] for v in sc0.values()])), "flag_share": FLAG}


def common_levels():
    """ONE scale for both branches: the score is calibrated, so Low / Moderate / High are thirds of ALL real UK validation vehicles (every fuel, four situations). With a scale per branch a "High"
    hybrid (27% real defects) would look worse than a "Moderate" petrol car (29%). Nothing is refitted; cuts come from val, the observed rates from test."""
    P = outcome_pairs()
    R, card = (json.loads(f.read_text(encoding="utf-8")) for f in (ROOT / "ml" / "model2_results.json", ART / "model2_card.json"))
    bri, d4 = card["brand_reliability_index"], card["dataset4_aggregation"]
    S = {}
    for branch, fuels in BRANCH_FUELS.items():
        m = joblib.load(ART / f"model2_{branch}_pipeline.joblib")
        for part in ("val", "test"):
            d = P[(P.part == part) & P.fuel.isin(fuels)].reset_index(drop=True)
            d["km_model1"] = model1_km(d)
            S[branch, part] = d.y.to_numpy(), real_scores(m, d, bri, d4, SYS_FEATURES[branch])
        # the score is calibrated per situation (what is known about the vehicle) on val: one common curve left the plate-only case, the usual one, slightly too high
        y = S[branch, "val"][0]
        card[branch]["platt_by_scenario"] = R[branch]["platt_by_scenario"] = {sc: list(platt(y, p)) for sc, p in S[branch, "val"][1].items()}
        R[branch]["val_calibration_error"] = {sc: {"one curve": reliability(y, apply_platt(p, card[branch]["platt"]))[1], "per situation": reliability(y, apply_platt(p, card[branch]["platt_by_scenario"][sc]))[1]}
                                              for sc, p in S[branch, "val"][1].items()}
        log(f"[{branch}] val calibration error {R[branch]['val_calibration_error']}")
        for part in ("val", "test"):
            S[branch, part] = S[branch, part][0], {sc: apply_platt(p, card[branch]["platt_by_scenario"][sc]) for sc, p in S[branch, part][1].items()}
    pooled = np.concatenate([v for b in BRANCH_FUELS for v in S[b, "val"][1].values()])
    cuts = [float(np.quantile(pooled, 1 / 3)), float(np.quantile(pooled, 2 / 3))]
    lv = lambda c: np.where(c <= cuts[0], 0, np.where(c <= cuts[1], 1, 2))
    for branch in BRANCH_FUELS:
        y, scores = S[branch, "test"]
        rates, shares, n = [], [], []
        for sc, c in scores.items():
            v = lv(c)
            q = R[branch]["test"]["uk"]["scenarios"][sc]
            q["reliability"], q["mean_calibration_error"] = reliability(y, c)
            q["level_share"] = [float((v == i).mean()) for i in range(3)]
            q["level_rate"] = [float(y[v == i].mean()) if (v == i).any() else None for i in range(3)]
        allv, ally = np.concatenate([lv(c) for c in scores.values()]), np.tile(y, len(scores))
        n = [int((allv == i).sum()) for i in range(3)]
        levels = {"cut_probabilities": cuts, "rule": "Low / Moderate / High = lowest, middle and highest third of all real UK vehicles (validation part, every fuel) by calibrated score: one scale for both branches",
                  "test_rate_by_level": [float(ally[allv == i].mean()) if n[i] else None for i in range(3)], "test_share_by_level": [x / len(allv) for x in n], "test_rows_by_level": n}
        R[branch]["levels"] = card[branch]["levels"] = levels
        card[branch]["mean_calibration_error"] = float(np.mean([R[branch]["test"]["uk"]["scenarios"][sc]["mean_calibration_error"] for sc in scores]))
        log(f"[{branch}] test calibration error {[(sc, round(R[branch]['test']['uk']['scenarios'][sc]['mean_calibration_error'], 3), [round(x, 2) for x in R[branch]['test']['uk']['scenarios'][sc]['level_share']]) for sc in scores]}")
        log(f"[{branch}] common levels {levels}")
    (ART / "model2_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    (ROOT / "ml" / "model2_results.json").write_text(json.dumps(R, indent=1, default=str), encoding="utf-8")


def main():
    P = outcome_pairs()
    NL = nl_outcomes()
    NL = NL[NL.age_year.between(3, 20)].reset_index(drop=True)
    bri, d4 = brand_index(P[P.part == "fit"]), d4_rates()
    D = load_d1(bri, d4)
    d5 = load_d5()
    tr, te = train_test_split(D, test_size=0.2, random_state=SEED, stratify=D.file + D.y.astype(str))
    days_pool = tr.days.to_numpy()
    R = {"flag_share": FLAG, "dataset1": {"rows": len(D), "by_file": D.file.value_counts().to_dict(), "train": len(tr), "test": len(te), "target_share_by_file": D.groupby("file").y.mean().to_dict()},
         "kaggle_sources": dict(SOURCE), "leakage_removed": {
             "Maintenance_Type": "determines the label exactly in the 250K file (Oil Check / Tire Rotation / Routine Inspection are always 0, every other type always 1)",
             "Days_Since_Last_Maintenance > 180": "IS the label rule of the 250K file (ROC-AUC 1.000 alone); kept because the PDF asks for it, but Dataset 1 has a limited share and its base rate is matched"}}
    card = {}
    for branch, fuels in BRANCH_FUELS.items():
        Q = P[P.fuel.isin(fuels)]
        fit, val, test = (Q[Q.part == p].reset_index(drop=True) for p in ("fit", "val", "test"))
        nl = NL[NL.fuel.isin(fuels)].reset_index(drop=True)
        for d in (val, test, nl):
            if len(d):
                d["km_model1"] = model1_km(d)
        pick = lambda d: d[(d.fuel != "electric") if branch == "ice" else (d.fuel == "electric")]
        R[branch] = {}
        card[branch] = train_branch(branch, fit, val, test, nl, pick(tr), pick(te), d5, bri, d4, days_pool, R[branch])
    prev_card = json.loads((PREV / "model2_card.json").read_text(encoding="utf-8"))
    card = {"name": "Model 2 - predictive maintenance classifier (Smart_Car_Models.pdf)", "version": "3.0.0", "trained_at": time.strftime("%Y-%m-%d"), **card, "features_ice": M2_FEATURES, "features_ev": M2_EV_FEATURES,
            "monotone_constraints": MONO, "brand_reliability_index": bri, "dataset4_aggregation": d4, "kaggle_sources": dict(SOURCE), "leakage_removed": R["leakage_removed"],
            "data_age_range": [3, 20], "target": "a defect is found at the next annual inspection (real UK outcome); Kaggle rows: Maintenance_Required / fault",
            "previous_version": {"version": prev_card["version"], "reported_dataset1_test_auc_affected_by_leakage": prev_card["ice"]["test"]["roc_auc"], "reported_dataset5_test_auc": prev_card["ev"]["test"]["roc_auc"]}}
    (ART / "model2_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    (ROOT / "ml" / "model2_results.json").write_text(json.dumps(R, indent=1, default=str), encoding="utf-8")
    common_levels()
    log("done")


if __name__ == "__main__":
    common_levels() if "--levels-only" in sys.argv else main()
