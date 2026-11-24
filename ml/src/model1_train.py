"""FINAL training of Model 1 (Smart_Car_Models.pdf) with data augmentation. Supersedes ml/archive/spec_model1.py.

Training data : Kaggle Datasets 7 + 8 + 3 (real, 80%) + SYNTHETIC vehicles (synthesis.py) generated from the FIT part of the official UK odometers.
Judged on     : (1) Kaggle listings never used (the same 20% as the previous model); (2) REAL odometers of official vehicles never used (val to choose, test once).
Experiments   : encoding (Target vs Frequency), algorithms (Linear, Ridge x 2 scalers, Random Forest, XGBoost), augmentation ablation, XGBoost tuning.
Choice rule   : lowest mean relative RMSE over the two REAL validation sets (MAE breaks ties). The shipped model is exactly the one tested (never refitted on test rows).

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/model1_train.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_lab import *  # noqa: E402,F403
import calibration as cal  # noqa: E402
import cbs_reference as cbs  # noqa: E402
import joblib  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402
from kaggle_sources import SOURCE  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.linear_model import LinearRegression, Ridge  # noqa: E402
from sklearn.preprocessing import MinMaxScaler  # noqa: E402

OUT = ROOT / "backend" / "app" / "ml" / "artifacts" / "spec"
X_COLS = M1_FEATURES + ["listing"]
N_SYNTH = 250_000
KAGGLE_WEIGHT = 6.0          # chosen on validation: keeps the listings performance while learning vehicles in use
LAMBDA = 0.1                 # ml/model1_transfer_shrinkage.json: 0 is best in both foreign markets, 0.1 costs < 0.6% RMSE and keeps the PDF features active
DATA_MAX_AGE, MIN_REAL = 25, 100
# UK cars are tested from their 3rd year (younger ones are mostly taxis), and 25-60% of the UK hybrids over 8 years old are Toyota Prius, largely ex private-hire
# (205,000 km at 9 years against 124,000 for every other hybrid): that part of the curve describes British taxis, so it is not used.
SUPPORT_MAX_AGE = {"hybrid": 8}
FUELS = ["petrol", "diesel", "hybrid", "electric", "lpg_cng"]
t0 = time.time()
log = lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True)


def full_prep(encoding, scaler=None):
    p = prep(encoding, scaler)
    p.transformers.append(("listing", "passthrough", ["listing"]))
    return p


def make(algo, encoding, **kw):
    if algo == "XGBoost (no scaling)":
        return Pipeline([("prep", full_prep(encoding)), ("model", xgb(**kw))])
    if algo == "Random Forest (no scaling)":
        return Pipeline([("prep", full_prep(encoding)), ("model", RandomForestRegressor(n_estimators=80, min_samples_leaf=10, max_features=0.5, max_samples=0.4, n_jobs=8, random_state=SEED))])
    est, sc = {"Linear Regression + StandardScaler": (LinearRegression(), StandardScaler()), "Ridge + StandardScaler": (Ridge(1.0), StandardScaler()),
               "Ridge + MinMaxScaler": (Ridge(1.0), MinMaxScaler())}[algo]
    return Pipeline([("prep", full_prep(encoding, sc)), ("model", est)])


def lookup_baselines(R, of, ot):
    """What a plain table (mean odometer of the real FIT vehicles) reaches on the same real test odometers: the model must be better than this."""
    R["test"]["baselines_on_official_test"] = {}
    for name, cols in (("table by age", ["age"]), ("table by age and fuel", ["age", "fuel"])):
        t = of.groupby(cols).km.mean().rename("p").reset_index()
        p = ot[cols].merge(t, on=cols, how="left").p.fillna(of.km.mean())
        R["test"]["baselines_on_official_test"][name] = metrics(ot.km, p)


def write_card(R, model, ot, kf, kv, kt):
    """The card the API, the tests and the documents read: experiments, tests on real data, and the previous version on exactly the same rows."""
    prev_card = json.loads((Path.home() / "smartcar_data" / "interim" / "previous_spec" / "model1_card.json").read_text(encoding="utf-8"))
    prev_real = json.loads((ROOT / "ml" / "previous_model1_on_real_odometers.json").read_text(encoding="utf-8"))
    same = ot.sample(6000, random_state=0)                                      # the same 6,000 vehicles previous_model1_eval.py drew
    p = model.predict(same[X_COLS])
    R["comparison_with_previous_version"] = {
        "kaggle_test (same 20% of the listings)": {"previous": {k: prev_card["chosen"]["held_out"]["test_" + k] for k in ("rmse", "mae", "r2")}, "new": R["test"]["kaggle_test"]},
        "real odometers (the same 6,000 official test vehicles)": {"previous": prev_real["all"], "new": metrics(same.km, p)},
        "interval_80pct_coverage_on_real_odometers": {"previous": prev_real["interval_80pct_coverage"], "new": R["interval_80pct_coverage_on_real_test_odometers"]},
        "cbs_joint_cell_mean_abs_pct_error": {"previous": prev_card["calibration"]["joint_cell_mean_abs_pct_error"], "new": R["calibration"]["joint_cell_mean_abs_pct_error"]}}
    rows = pd.concat([kf, kv, kt]).source.value_counts().to_dict()
    card = {"name": "Model 1 - odometer regression (Smart_Car_Models.pdf)", "version": "3.0.0", "trained_at": time.strftime("%Y-%m-%d"), "kaggle_sources": R["data"]["kaggle_sources"], "rows_by_dataset": {k: int(v) for k, v in rows.items()},
            "synthetic_training_rows": R["data"]["synthetic_training_rows"], "synthetic_fidelity": R["synthetic_fidelity"], "features": M1_FEATURES, "encoding_experiment": {"scores": R["experiment_1_encoding"], "chosen": R["experiment_1_chosen"]},
            "algorithm_experiment": {"scores": R["experiment_2_algorithms"], "chosen": R["experiment_2_chosen"], "rule": "lowest mean relative RMSE over the two REAL validation sets (Kaggle listings, official odometers)"},
            "augmentation_experiment": R["experiment_3_augmentation"], "chosen": {k: R["final"][k] for k in ("algorithm", "encoding", "params", "kaggle_weight", "lambda")}, "overfitting_check": R["overfitting_check"], "test": R["test"],
            "comparison_with_previous_version": R["comparison_with_previous_version"], "interval_80pct_heldout_coverage": R["interval_80pct_coverage_on_real_test_odometers"], "calibration": R["calibration"],
            "support_max_age": SUPPORT_MAX_AGE, "note_owner_type": prev_card["note_owner_type"],
            "limitations": ["no Israeli odometers are published: the Israeli level comes from CBS averages, individual errors in Israel cannot be measured", "electric vehicles: no CBS figure, always low reliability",
                            "hybrids over 8 years: the real UK curve is mostly former taxis and is not used"]}
    (OUT / "model1_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")


def calibrate_only():
    """Re-run only the Israeli localisation with the saved pipeline (the regression and its test results do not change)."""
    R = json.loads((ROOT / "ml" / "model1_results.json").read_text(encoding="utf-8"))
    model = joblib.load(OUT / "model1_pipeline.joblib")
    o = odometers().assign(listing=0.0)
    of, ov, ot = (o[o.part == p].reset_index(drop=True) for p in ("fit", "val", "test"))
    so, _ = synth_official(of, N_SYNTH, seed=7)
    so["listing"] = 0.0
    calibrate(model, so, of, ov, ot, R)
    lookup_baselines(R, of, ot)
    write_card(R, model, ot, *kaggle())
    (ROOT / "ml" / "model1_results.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    log("done")


def main():
    R = {}
    kf, kv, kt = kaggle()
    o = odometers()
    of, ov, ot = (o[o.part == p].reset_index(drop=True) for p in ("fit", "val", "test"))
    for d in (kf, kv, kt):
        d["listing"], d["synthetic"] = 1.0, False
    ov["listing"] = ot["listing"] = 0.0
    ovs = ov.sample(60_000, random_state=0)
    so, gen = synth_official(of, N_SYNTH, seed=7)
    so["listing"] = 0.0
    sk = synth_kaggle(kf, 60_000)
    sk["listing"] = 1.0
    ro = of.sample(N_SYNTH, random_state=1).assign(listing=0.0, synthetic=False)
    R["data"] = {"kaggle_train": len(kf), "kaggle_val": len(kv), "kaggle_test": len(kt), "kaggle_sources": dict(SOURCE), "official_fit (generator only)": len(of), "official_val": len(ov), "official_test": len(ot),
                 "synthetic_training_rows": len(so)}
    R["synthetic_fidelity"] = {"official (against real vehicles the generator never saw)": fidelity(ov, so, ["age", "engine_cc", "km"], ["fuel", "make_model"]),
                               "kaggle": fidelity(kv, sk, ["age", "engine_cc", "km"], ["fuel", "make_model"])}
    log(f"synthetic ready {len(so):,}; KS {R['synthetic_fidelity']['official (against real vehicles the generator never saw)']['ks_statistic']}")

    def train(parts, algo="XGBoost (no scaling)", enc="frequency", **kw):
        T = pd.concat([p[KEEP + ["listing"]] for p in parts], ignore_index=True)
        return make(algo, enc, **kw).fit(T[X_COLS], T.km, model__sample_weight=np.where(T.listing == 1, KAGGLE_WEIGHT, 1.0)), T

    def val(m):
        a, b = metrics(kv.km, m.predict(kv[X_COLS])), metrics(ovs.km, m.predict(ovs[X_COLS]))
        return {"kaggle_val": a, "official_val": b, "score": (a["rmse"] / 21_800 + b["rmse"] / 47_500) / 2}

    def show(name, v):
        log(f"{name:44s} kaggle RMSE {v['kaggle_val']['rmse']:7,.0f} R2 {v['kaggle_val']['r2']:.3f} | real odometers RMSE {v['official_val']['rmse']:7,.0f} R2 {v['official_val']['r2']:.3f} | score {v['score']:.4f}")

    R["experiment_1_encoding"] = {}
    for enc in ("target", "frequency"):
        m, _ = train([kf, so], enc=enc)
        R["experiment_1_encoding"][enc] = val(m)
        show("encoding " + enc, R["experiment_1_encoding"][enc])
    enc = min(R["experiment_1_encoding"], key=lambda k: R["experiment_1_encoding"][k]["score"])
    R["experiment_1_chosen"] = enc

    R["experiment_2_algorithms"] = {}
    for algo in ("Linear Regression + StandardScaler", "Ridge + StandardScaler", "Ridge + MinMaxScaler", "Random Forest (no scaling)", "XGBoost (no scaling)"):
        m, _ = train([kf, so], algo, enc)
        R["experiment_2_algorithms"][algo] = val(m)
        show(algo, R["experiment_2_algorithms"][algo])
    algo = min(R["experiment_2_algorithms"], key=lambda k: R["experiment_2_algorithms"][k]["score"])
    R["experiment_2_chosen"] = algo

    R["experiment_3_augmentation"] = {}
    for name, parts in {"Kaggle only (no augmentation)": [kf], "Kaggle + synthetic Kaggle": [kf, sk], "Kaggle + synthetic official (chosen)": [kf, so], "Kaggle + real official rows (reference, not used)": [kf, ro]}.items():
        m, _ = train(parts, enc=enc)
        R["experiment_3_augmentation"][name] = val(m)
        show(name, R["experiment_3_augmentation"][name])

    grid = [dict(), dict(max_depth=7, min_child_weight=60, n_estimators=700, learning_rate=0.04, reg_lambda=10), dict(max_depth=8, min_child_weight=100, n_estimators=600, learning_rate=0.04, reg_lambda=20),
            dict(max_depth=6, min_child_weight=100, n_estimators=900, learning_rate=0.03, reg_lambda=20), dict(max_depth=7, min_child_weight=150, n_estimators=900, learning_rate=0.03, reg_lambda=20, colsample_bytree=0.6)]
    R["experiment_4_tuning"], best = [], None
    for kw in grid:
        m, T = train([kf, so], enc=enc, **kw)
        v = val(m)
        R["experiment_4_tuning"].append({"params": kw, **v})
        show("XGBoost " + json.dumps(kw)[:34], v)
        if best is None or v["score"] < best[0]:
            best = (v["score"], kw, m, T)
    _, kw, model, T = best
    R["final"] = {"algorithm": algo, "encoding": enc, "params": kw, "kaggle_weight": KAGGLE_WEIGHT, "lambda": LAMBDA}
    if not algo.startswith("XGBoost"):
        model, T = train([kf, so], algo, enc)
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUT / "model1_pipeline.joblib", compress=3)

    # over-fitting: the same metric on rows it was trained on and on real rows it never saw
    s_fit = of.sample(60_000, random_state=3).assign(listing=0.0)
    R["overfitting_check"] = {"kaggle_train_r2": metrics(kf.km, model.predict(kf[X_COLS]))["r2"], "kaggle_val_r2": metrics(kv.km, model.predict(kv[X_COLS]))["r2"],
                              "synthetic_train_r2": metrics(so.km, model.predict(so[X_COLS]))["r2"], "official_fit_real_r2": metrics(s_fit.km, model.predict(s_fit[X_COLS]))["r2"],
                              "official_val_real_r2": metrics(ovs.km, model.predict(ovs[X_COLS]))["r2"]}
    log(f"over-fitting check {R['overfitting_check']}")

    # ---------------- final test, once
    p_o = np.clip(model.predict(ot[X_COLS]), 0, None)
    R["test"] = {"kaggle_test": metrics(kt.km, model.predict(kt[X_COLS])), "official_test": metrics(ot.km, p_o), "official_test_by_age": {}, "official_test_by_fuel": {}}
    for lo, hi in ((1, 3), (4, 6), (7, 9), (10, 13), (14, 25)):
        k = ot.age.between(lo, hi).to_numpy()
        R["test"]["official_test_by_age"][f"{lo}-{hi}"] = metrics(ot.km[k], p_o[k])
    for f in FUELS:
        k = (ot.fuel == f).to_numpy()
        R["test"]["official_test_by_fuel"][f] = metrics(ot.km[k], p_o[k])
    log(f"FINAL TEST kaggle {R['test']['kaggle_test']} | real odometers {R['test']['official_test']}")
    calibrate(model, so, of, ov, ot, R)
    lookup_baselines(R, of, ot)
    write_card(R, model, ot, kf, kv, kt)
    (ROOT / "ml" / "model1_results.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    log("done")


def calibrate(model, so, of, ov, ot, R):
    """Israeli localisation: official level (CBS), learned shape by fuel, shrunk individual effect; indicative 80% range from real odometers."""
    p_s = np.clip(model.predict(so[X_COLS]), 500, None)
    af = {}
    for f in FUELS:
        k = (so.fuel == f).to_numpy()
        g = pd.Series(p_s[k]).groupby(so.age[k].round().astype(int).to_numpy()).agg(["mean", "size"]).reindex(range(0, DATA_MAX_AGE + 1))
        c = g["mean"].where(g["size"] >= 20)
        if c.notna().sum() < 5:                              # LPG / CNG: a few hundred real vehicles; converted petrol cars -> the petrol curve (always flagged as low reliability)
            af[f] = af["petrol"].copy()
            continue
        c = c.interpolate(limit_direction="both")
        c = c.rolling(3, center=True, min_periods=1).mean()
        c.iloc[0] = c.iloc[1] * 0.4
        af[f] = np.maximum.accumulate(c.to_numpy())
    raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
    raw = raw[raw.sug_degem == "P"].copy()
    il = normalise_registry(raw, reference_year=2026)
    for c in ("tozeret_cd", "degem_cd", "shnat_yitzur", "kinuy_mishari"):
        il[c] = raw[c].to_numpy()
    w = pd.read_csv(INTERIM_DIR / "wltp_models.csv").drop_duplicates(["tozeret_cd", "degem_cd", "shnat_yitzur"])
    il = il.merge(w[["tozeret_cd", "degem_cd", "shnat_yitzur", "nefah_manoa", "automatic_ind"]], on=["tozeret_cd", "degem_cd", "shnat_yitzur"], how="left")
    il = il[il.fuel.isin(FUELS) & (il.age >= 1)].reset_index(drop=True)
    il["a"] = il.age.clip(upper=DATA_MAX_AGE).astype(int)
    # reference curve: the average Israeli vehicle of each age (its own fuel mix), from vehicles within 2 years of that age
    ref = np.array([np.mean([af[f][a] for f in il.fuel[(il.a - a).abs() <= 2]]) if ((il.a - a).abs() <= 2).any() else np.nan for a in range(DATA_MAX_AGE + 1)])
    shape = {f: (af[f] / ref) for f in FUELS}
    counts = {f: [int(((of.fuel == f) & ((of.age - a).abs() <= 1)).sum()) for a in range(DATA_MAX_AGE + 1)] for f in FUELS}
    for f in FUELS:                                          # the shape is only read where the real data support it and held constant elsewhere
        hi = SUPPORT_MAX_AGE.get(f) or max([a for a in range(3, DATA_MAX_AGE + 1) if counts[f][a] >= MIN_REAL], default=3)
        shape[f][:3], shape[f][hi:] = shape[f][3], shape[f][hi]
    X = pd.DataFrame({"age": il.a, "engine_cc": np.where(il.fuel == "electric", 0.0, il.nefah_manoa.where(il.nefah_manoa > 0)), "automatic": il.automatic_ind, "fuel": il.fuel, "owner_type": "Unknown",
                      "make_model": [make_model_key(a, b) for a, b in zip(il.make, il.kinuy_mishari)], "listing": 0.0})
    ratio = np.clip(np.clip(model.predict(X[X_COLS]), 0, None) / np.array([af[f][a] for f, a in zip(il.fuel, il.a)]), 0.5, 2.0)
    rates22 = {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}
    rates = np.array([rates22[cbs.age_to_band(a)] * 1000 for a in range(cal.MAX_AGE + 1)])
    annual = rates[il.age.clip(upper=cal.MAX_AGE).astype(int)] * np.array([shape[f][a] for f, a in zip(il.fuel, il.a)]) * ratio ** LAMBDA
    il["own_cbs"], il["band"] = il.ownership.map(cbs.REGISTRY_OWNERSHIP_TO_CBS), il.age.map(cbs.age_to_band)
    fuel_cbs = il.fuel.map({"petrol": "gasoline", "diesel": "diesel", "hybrid": "hybrid", "lpg_cng": "gas_lpg"})
    T = {"age": rates22, "own": {k: cbs.CBS_OWNERSHIP_2022[k]["all"] for k in ("private", "leasing", "company", "rental")}, "fuel": dict(cbs.CBS_FUEL_2022)}
    G = {"age": il.band.to_numpy(), "own": il.own_cbs.to_numpy(), "fuel": fuel_cbs.to_numpy()}
    new = (il.age <= 3).to_numpy()

    def joint(mult):
        out = []
        for k in ("private", "leasing", "company", "rental"):
            for grp, mask in (("new", new), ("old", ~new)):
                s = (G["own"] == k) & mask
                if s.sum() >= 15:
                    v, tgt = float((annual * mult)[s].mean() / 1000), cbs.CBS_OWNERSHIP_2022[k][grp]
                    out.append({"ownership": k, "age_group": grp, "n": int(s.sum()), "model": v, "cbs": tgt, "abs_pct_error": abs(v / tgt - 1) * 100})
        return out, float(np.mean([c["abs_pct_error"] for c in out]))

    fac2, mult2 = cal.rake_means(annual / 1000, G, T, ["age", "own"])
    fuel_before = {k: float((annual * mult2)[G["fuel"] == k].mean() / 1000) for k in T["fuel"] if (G["fuel"] == k).any()}
    fac, mult = cal.rake_means(annual / 1000, G, T, ["age", "own", "fuel"])
    cells2, err2 = joint(mult2)
    cells, err = joint(mult)
    unmapped = {k: float(il[il.fuel == k].shape[0]) for k in FUELS}
    f_fuel = {"petrol": fac["fuel"]["gasoline"], "diesel": fac["fuel"]["diesel"], "hybrid": fac["fuel"]["hybrid"], "lpg_cng": fac["fuel"]["gas_lpg"]}
    f_fuel["electric"] = 1.0                                     # CBS publishes no electric figure: neutral, and flagged as low reliability
    R["calibration"] = {"source": "CBS Publication 1923: Tables 4 (age) and 8 (ownership), section 2.2 (propulsion)", "registry_vehicles": len(il), "by_fuel": unmapped,
                        "propulsion_check_before_using_it": {"model": fuel_before, "cbs": T["fuel"]}, "joint_cell_error_age_ownership_only": err2, "held_out_joint_cells": cells,
                        "joint_cell_mean_abs_pct_error": err, "factors": fac, "share_official_engine_data": float(il.nefah_manoa.notna().mean())}
    # indicative 80% range: how REAL vehicles spread around the estimate (val part), coverage measured on the test part
    def spread(d):
        p = np.clip(model.predict(d[X_COLS]), 0, None)
        m_ = np.array([af[f][a] for f, a in zip(d.fuel, d.age.clip(upper=DATA_MAX_AGE))])
        return d.km.to_numpy() / (m_ * np.clip(p / m_, 0.5, 2.0) ** LAMBDA)
    rv, rt = spread(ov), spread(ot)
    bands_v, bands_t = ov.age.map(cbs.age_to_band).to_numpy(), ot.age.map(cbs.age_to_band).to_numpy()
    q = {}
    for f in FUELS:
        kf_ = (ov.fuel == f).to_numpy()
        q[f] = {"all": [float(np.quantile(rv[kf_], 0.1)), float(np.quantile(rv[kf_], 0.9))]}
        for b in cbs.BAND_LABELS:
            s = kf_ & (bands_v == b)
            if s.sum() >= 150:
                q[f][b] = [float(np.quantile(rv[s], 0.1)), float(np.quantile(rv[s], 0.9))]
    lo = np.array([q[f].get(b, q[f]["all"])[0] for f, b in zip(ot.fuel, bands_t)])
    hi = np.array([q[f].get(b, q[f]["all"])[1] for f, b in zip(ot.fuel, bands_t)])
    R["interval_80pct_coverage_on_real_test_odometers"] = float(((rt >= lo) & (rt <= hi)).mean())
    cj = {"max_age": cal.MAX_AGE, "data_max_age": DATA_MAX_AGE, "lambda": LAMBDA, "rates_km_by_age": rates.tolist(), "age_bands": [list(b) for b in cbs.AGE_BANDS], "age_band_labels": cbs.BAND_LABELS,
          "age_band_factors": fac["age"], "ownership_factors": fac["own"], "fuel_factors": f_fuel, "registry_ownership_to_cbs": cbs.REGISTRY_OWNERSHIP_TO_CBS,
          "age_fuel_mean": {f: v.tolist() for f, v in af.items()}, "age_fuel_shape": {f: v.tolist() for f, v in shape.items()}, "interval_ratio_quantiles": q,
          "real_vehicles_by_fuel_age": counts, "min_real_vehicles": MIN_REAL, "support_max_age": SUPPORT_MAX_AGE}
    (OUT / "model1_calibration.json").write_text(json.dumps(cj), encoding="utf-8")
    R["real_vehicles_by_fuel_age"] = counts
    log(f"calibration: joint cells {err2:.1f}% (age+ownership) -> {err:.1f}% (+propulsion); propulsion before {fuel_before}; 80% range covers {R['interval_80pct_coverage_on_real_test_odometers']:.1%} of real test odometers; factors {fac}")


if __name__ == "__main__":
    calibrate_only() if "--calibrate-only" in sys.argv else main()
