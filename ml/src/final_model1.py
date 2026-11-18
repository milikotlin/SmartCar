"""FINAL training + export of Model 1 (odometer estimate), approved design.

Design (Sprint 3 notebooks 01 and 03, approved by the student):
  * data: Datasets 7 (UK) + 8 (India) + 3 (Cardekho), cleaned as in notebook 01 (units in km, duplicates removed);
  * algorithm: XGBoost regression on age + fuel, forced to be non-decreasing in age;
  * calibration: yearly increments of the learned age curve are rescaled by iterative proportional fitting so the population means on a random
    sample of the real Israeli registry equal the official CBS means by age band and ownership (CBS Publication 1923, Tables 4 and 8);
    above the age supported by the training data the official CBS yearly rate replaces the (flat) learned increment;
  * uncertainty: 10% and 90% quantile XGBoost models (age + fuel) scaled by the same calibration ratio -> an indicative 80% range.

Exports (backend/app/ml/artifacts/model1/): mean_model.json, q10_model.json, q90_model.json (native XGBoost JSON), calibration.json, model1_card.json.
Run:  ml/.venv/Scripts/python.exe -I -X utf8 ml/src/final_model1.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration as cal  # noqa: E402
import cbs_reference as cbs  # noqa: E402
import mileage_data as md  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "backend" / "app" / "ml" / "artifacts" / "model1"
FUELS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]      # fixed feature order: [age, fuel_diesel, ..., fuel_petrol]
SEED = 42


def design(df: pd.DataFrame) -> np.ndarray:
    x = np.zeros((len(df), 1 + len(FUELS)), dtype=np.float32)
    x[:, 0] = df["age"].to_numpy(dtype=np.float32)
    for j, f in enumerate(FUELS):
        x[:, 1 + j] = (df["fuel"].to_numpy() == f)
    return x


def mean_model() -> xgb.XGBRegressor:
    # same hyper-parameters as notebook 01 ("xgb"), plus the monotone constraint of notebook 03 (age only)
    return xgb.XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                            tree_method="hist", n_jobs=8, random_state=SEED, monotone_constraints=tuple([1] + [0] * len(FUELS)))


def quantile_model(q: float) -> xgb.XGBRegressor:
    return xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=q, n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                            tree_method="hist", n_jobs=8, random_state=0)


def grid(models_predict) -> dict:
    """fuel -> predictions for ages 0..MAX_AGE."""
    out = {}
    for f in FUELS:
        g = pd.DataFrame({"age": np.arange(0, cal.MAX_AGE + 1), "fuel": f})
        out[f] = np.clip(models_predict(design(g)), 0, None)
    return out


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    clean = {k: md.load_clean(k)[0] for k in ["d7_uk", "d8_in", "d3_cardekho"]}
    P = pd.concat(clean.values(), ignore_index=True)
    P = P[P.fuel.isin(FUELS)].reset_index(drop=True)
    print(f"training data 7+8+3: {len(P):,} rows", {k: len(v) for k, v in clean.items()})

    # --- 1. held-out validation of the learned model (80/20, stratified by source, as in notebook 03)
    tr, te = train_test_split(P, test_size=0.2, random_state=SEED, stratify=P["source"])
    mv = mean_model().fit(design(tr), tr.km)
    pred = np.clip(mv.predict(design(te)), 0, None)
    resid = te.km.to_numpy() - pred
    metrics = {"R2": float(1 - np.sum(resid ** 2) / np.sum((te.km - te.km.mean()) ** 2)), "RMSE_km": float(np.sqrt(np.mean(resid ** 2))), "MAE_km": float(np.mean(np.abs(resid))), "n_test": int(len(te))}
    q10v, q90v = quantile_model(0.1).fit(design(tr), tr.km), quantile_model(0.9).fit(design(tr), tr.km)
    lo, hi = np.minimum(q10v.predict(design(te)), q90v.predict(design(te))), np.maximum(q10v.predict(design(te)), q90v.predict(design(te)))
    metrics["raw_80pct_interval_coverage_heldout"] = float(((te.km >= lo) & (te.km <= hi)).mean())
    print("held-out (uncalibrated, training markets):", metrics)

    # --- 2. final models on ALL training rows
    mm = mean_model().fit(design(P), P.km)
    q10, q90 = quantile_model(0.1).fit(design(P), P.km), quantile_model(0.9).fit(design(P), P.km)
    mm.get_booster().save_model(OUT / "mean_model.json")
    q10.get_booster().save_model(OUT / "q10_model.json")
    q90.get_booster().save_model(OUT / "q90_model.json")

    # --- 3. CBS calibration (age band x ownership) on the real Israeli registry sample
    curves_raw = grid(mm.predict)
    curves = {f: np.maximum.accumulate(c) for f, c in curves_raw.items()}                 # cumulative odometer by age, non-decreasing
    a_sup = cal.supported_max_age(P.age)
    rates22 = {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}
    rates_km = np.array([rates22[cbs.age_to_band(a)] * 1000 for a in range(cal.MAX_AGE + 1)])
    il = normalise_registry(pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv"), reference_year=2026)
    il = il[il.age >= 1].reset_index(drop=True)
    il["own_cbs"] = il.ownership.map(cbs.REGISTRY_OWNERSHIP_TO_CBS)
    il["band"] = il.age.map(cbs.age_to_band)
    base = cal.implied_annual(curves, il.fuel, il.age, a_sup, rates_km)
    T = {"age": rates22, "own": {o: cbs.CBS_OWNERSHIP_2022[o]["all"] for o in ["private", "leasing", "company", "rental"]}}
    G = {"age": il.band.to_numpy(), "own": il.own_cbs.to_numpy()}
    factors, mult = cal.rake_means(base / 1000, G, T, ["age", "own"])
    implied = base * mult
    marg = {}
    for fam in ["age", "own"]:
        for cat, tgt in T[fam].items():
            m = G[fam] == cat
            marg[f"{fam}:{cat}"] = {"n_registry_sample": int(m.sum()), "model_thousand_km_per_year": float(implied[m].mean() / 1000) if m.any() else None, "cbs_2022": float(tgt)}
    # joint cells of CBS Table 8 (ownership x new/old), never used in the fit
    new = (il.age <= 3).to_numpy()
    cells = []
    for o in ["private", "leasing", "company", "rental"]:
        for grp, mask in [("new", new), ("old", ~new)]:
            m = (G["own"] == o) & mask
            if m.sum() >= 15:
                tgt = cbs.CBS_OWNERSHIP_2022[o][grp]
                cells.append({"ownership": o, "age_group": grp, "n": int(m.sum()), "model": float(implied[m].mean() / 1000), "cbs": float(tgt), "abs_pct_error": float(abs(implied[m].mean() / 1000 / tgt - 1) * 100)})
    cell_err = float(np.mean([c["abs_pct_error"] for c in cells]))
    print(f"calibration: A_SUP={a_sup}; mean abs % error on {len(cells)} held-out Table-8 joint cells = {cell_err:.1f}%; fleet mean implied {implied.mean()/1000:.1f} (CBS 15.2 / 14.7)")

    # --- 4. final calibrated curves for every fuel x ownership x age (what the API serves) and the interval ratios
    mean_curve, q10_curve, q90_curve = curves_raw, grid(q10.predict), grid(q90.predict)
    cal_json = {
        "max_age": cal.MAX_AGE, "fuels": FUELS, "a_sup": int(a_sup), "rates_km_by_age": [float(x) for x in rates_km],
        "age_band_factors": {k: float(v) for k, v in factors["age"].items()}, "ownership_factors": {k: float(v) for k, v in factors["own"].items()},
        "age_bands": [list(b) for b in cbs.AGE_BANDS], "age_band_labels": cbs.BAND_LABELS,
        "learned_curve_cumulative_km": {f: [float(x) for x in c] for f, c in curves.items()},
        "q10_curve_km": {f: [float(x) for x in c] for f, c in q10_curve.items()}, "q90_curve_km": {f: [float(x) for x in c] for f, c in q90_curve.items()},
        "fuel_alias": cal.FUEL_ALIAS, "registry_ownership_to_cbs": cbs.REGISTRY_OWNERSHIP_TO_CBS, "reference_year_for_factors": 2026,
    }
    (OUT / "calibration.json").write_text(json.dumps(cal_json), encoding="utf-8")

    # a few reference points for the unit tests / model card (computed with the SAME functions the API will use)
    ref = []
    for fuel, own, age in [("petrol", "private", 3), ("petrol", "private", 10), ("diesel", "company", 7), ("petrol", "leasing", 5), ("hybrid", "private", 6)]:
        est = float(cal.calibrated_odometer(curves, factors, [fuel], [age], [own], None, a_sup, rates_km)[0])
        ref.append({"fuel": fuel, "ownership": own, "age": age, "calibrated_km": est, "learned_uncalibrated_km": float(curves[fuel][age])})
    data_hash = hashlib.sha256(pd.util.hash_pandas_object(P[["make", "age", "fuel", "km"]], index=False).to_numpy().tobytes()).hexdigest()
    card = {
        "name": "Model 1 - odometer estimate (kilometres driven)", "version": "1.0.0", "trained_at": time.strftime("%Y-%m-%d"),
        "training_data": {"datasets": {"7 UK used cars": len(clean["d7_uk"]), "8 India used cars": len(clean["d8_in"]), "3 Cardekho": len(clean["d3_cardekho"])}, "rows": int(len(P)), "sha256_of_rows": data_hash,
                          "units": "UK odometers converted from miles to km; ages computed against each dataset's own snapshot year"},
        "algorithm": "XGBoost regression, features age + fuel, monotone non-decreasing in age; q10/q90 XGBoost quantile models for the range",
        "held_out_validation_uncalibrated": metrics,
        "calibration": {"source": "CBS Publication 1923 (Vehicle Kilometers Travelled 2022), Tables 4 and 8; fleet mean 15.2 (2022) / 14.7 (2023-24)", "families": ["age band", "ownership"], "supported_age": int(a_sup),
                        "registry_sample_rows": int(len(il)), "marginals": marg, "held_out_joint_cells": cells, "joint_cell_mean_abs_pct_error": cell_err},
        "reference_points": ref,
        "interval": "indicative 80% range: quantile models scaled by calibrated/learned ratio; coverage of the raw range on held-out training-market vehicles is in held_out_validation_uncalibrated; NOT validated on Israeli vehicles",
        "limitations": ["no per-vehicle Israeli odometer data exist in open form: individual accuracy in Israel is unknown",
                        "calibration fixes the level of population means (age band x ownership); it does not narrow the spread of individual vehicles",
                        "assumes yearly usage is stationary across cohorts; electric vehicles are treated like petrol (CBS has no EV data); registry sample ages are as of 2026",
                        "make/model are not used (no measurable value in experiments)"],
        "library_versions": {"xgboost": xgb.__version__, "numpy": np.__version__, "pandas": pd.__version__},
    }
    (OUT / "model1_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(f"exported to {OUT} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
