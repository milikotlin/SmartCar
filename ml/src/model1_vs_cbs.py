"""READ-ONLY evaluation of Model 1 against simple baselines built only from official CBS data. Nothing is retrained or exported.

Part A - coherence for Israeli vehicles (no individual ground truth exists in open data): the final Model 1 (as the API serves it) against three CBS-only estimates on
         a random sample of the Israeli registry: (B1) cumulative CBS yearly rates by age band; (B2) B1 x CBS ownership mean; (B3) B2 x CBS propulsion mean.
Part B - what the learned model adds, measured where individual ground truth exists: leave-one-market-out. Train on two used-car markets, calibrate with the AGGREGATES
         of the third (age-band means: the analogue of an official table), evaluate on individual vehicles of the third. Baselines use exactly the same aggregates.

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/model1_vs_cbs.py   (writes ml/model1_vs_cbs_results.json)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
import calibration as cal  # noqa: E402
import cbs_reference as cbs  # noqa: E402
import mileage_data as md  # noqa: E402
import mileage_experiments as mx  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402
from app.ml.mileage import MileageModel  # noqa: E402

OUT = {}

# ====================================================================== Part A
m1 = MileageModel(ROOT / "backend" / "app" / "ml" / "artifacts")
raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
raw = raw[raw.sug_degem == "P"].copy()
il = normalise_registry(raw, reference_year=2026)
il = il[il.fuel.notna() & (il.age >= 0) & (il.age <= 40)].reset_index(drop=True)
il["own"] = il.ownership
rates = {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}
# CBS-only estimate of the odometer of a vehicle of age A: A full years of driving at the official yearly rate of the age band of each year (years 1..A).
# (cal.cbs_cumulative_expected also counts a full year for age 0, which would add one year of driving to every vehicle: that bias is removed here)
b1_curve = cal.cbs_cumulative_expected(rates) - rates["0-3"] * 1000
own_mean = {o: cbs.CBS_OWNERSHIP_2022[o]["all"] for o in ("private", "leasing", "company", "rental")}
fleet = cbs.CBS_OWNERSHIP_2022["total"]["all"]
fuel_mean = cbs.CBS_FUEL_2022
fuel_key = {"petrol": "gasoline", "diesel": "diesel", "hybrid": "hybrid", "lpg_cng": "gas_lpg"}
est, b1, b2, b3, lo, hi = [], [], [], [], [], []
for r in il.itertuples():
    a = int(min(r.age, cal.MAX_AGE))
    e = m1.estimate(r.fuel, int(r.age), r.own)
    est.append(e.km); lo.append(e.km_low); hi.append(e.km_high)
    x1 = b1_curve[a]
    own = cbs.REGISTRY_OWNERSHIP_TO_CBS.get(r.own)
    x2 = x1 * (own_mean[own] / fleet if own else 1.0)
    fk = fuel_key.get(r.fuel)
    x3 = x2 * (fuel_mean[fk] / fleet if fk else 1.0)
    b1.append(x1); b2.append(x2); b3.append(x3)
il["m1"], il["b1"], il["b2"], il["b3"], il["lo"], il["hi"] = est, b1, b2, b3, lo, hi
d = il[il.age >= 1].copy()


def summ(name, col):
    ratio = d.m1 / d[col]
    return {"baseline": name, "median ratio Model 1 / baseline": float(ratio.median()), "median |difference| %": float((ratio - 1).abs().median() * 100),
            "share within 10%": float(((ratio - 1).abs() <= 0.10).mean()), "share differing by more than 25%": float(((ratio - 1).abs() > 0.25).mean()),
            "Spearman correlation": float(d.m1.corr(d[col], method="spearman"))}


OUT["A_agreement_with_cbs_only_estimates"] = [summ("B1 CBS age bands", "b1"), summ("B2 + CBS ownership", "b2"), summ("B3 + CBS propulsion", "b3")]
fleet_mean_annual = {"Model 1": float((d.m1 / d.age).mean() / 1000), "B1": float((d.b1 / d.age).mean() / 1000), "B2": float((d.b2 / d.age).mean() / 1000), "B3": float((d.b3 / d.age).mean() / 1000), "CBS fleet 2022 / 2023-24": [15.2, 14.7]}
OUT["A_mean_annual_km_thousand_age_ge_1"] = fleet_mean_annual
grp = []
for key, col in (("fuel", "fuel"), ("ownership", "own")):
    for val, g in d.groupby(col):
        if len(g) >= 30:
            grp.append({"group": f"{key}: {val}", "n": int(len(g)), "Model 1 mean annual km": float((g.m1 / g.age).mean()), "B3 mean annual km": float((g.b3 / g.age).mean()),
                        "CBS published mean": (fuel_mean.get(fuel_key.get(val)) * 1000 if key == "fuel" and fuel_key.get(val) else (own_mean.get(cbs.REGISTRY_OWNERSHIP_TO_CBS.get(val)) * 1000 if key == "ownership" and cbs.REGISTRY_OWNERSHIP_TO_CBS.get(val) else None))})
OUT["A_by_group"] = grp
d["rel_width"] = (d.hi - d.lo) / d.m1
d["band"] = d.age.map(cbs.age_to_band)
OUT["A_interval_relative_width_by_age_band"] = {b: {"median (high-low)/estimate": float(g.rel_width.median()), "median low": float(g.lo.median()), "median estimate": float(g.m1.median()), "median high": float(g.hi.median())} for b, g in d.groupby("band")}
OUT["A_annual_km_percentiles"] = {str(q): float(np.percentile(d.m1 / d.age, q)) for q in (1, 5, 50, 95, 99)}
bycombo = []
for fuel in ("petrol", "diesel", "hybrid"):
    for own in ("private", "leasing", "company", "rental"):
        for age in (3, 7, 12):
            e = m1.estimate(fuel, age, own)
            bycombo.append({"fuel": fuel, "ownership": own, "age": age, "estimate": e.km, "low": e.km_low, "high": e.km_high, "annual": e.annual_km})
OUT["A_grid_fuel_ownership_age"] = bycombo
print("Part A done", flush=True)
if "--only-a" in sys.argv:                                   # re-run Part A only and merge into the existing results file
    prev = json.loads((ROOT / "ml" / "model1_vs_cbs_results.json").read_text(encoding="utf-8"))
    prev.update({k: v for k, v in OUT.items() if k.startswith("A_")})
    (ROOT / "ml" / "model1_vs_cbs_results.json").write_text(json.dumps(prev, indent=1), encoding="utf-8")
    sys.exit(0)

# ====================================================================== Part B
clean = {k: md.load_clean(k)[0] for k in md.LOADERS}
IN = pd.concat([clean["d8_in"], clean["d3_cardekho"]], ignore_index=True)
MARKETS = {"UK": clean["d7_uk"], "India": IN, "US": clean["d6_craigslist"]}
BANDS = cbs.BAND_LABELS
bandof = lambda s: s.map(cbs.age_to_band).to_numpy()
FUEL_CATS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]


def quantile_model(df, q):
    pipe = mx.build_pipeline(numeric=["age"], low_card=["fuel"], make_enc=None, algo="xgb")
    pipe.set_params(est=XGBRegressor(objective="reg:quantileerror", quantile_alpha=q, n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8, tree_method="hist", n_jobs=8, random_state=0))
    return pipe.fit(df, df.km)


def metrics(y, p):
    p = np.clip(p, 0, None)
    return {"RMSE": float(np.sqrt(np.mean((y - p) ** 2))), "MAE": float(np.mean(np.abs(y - p))), "R2": float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)), "bias": float(np.mean(p - y))}


rowsB = []
for tgt in MARKETS:
    calib, test = train_test_split(MARKETS[tgt], test_size=0.5, random_state=0)
    train = pd.concat([MARKETS[m] for m in MARKETS if m != tgt], ignore_index=True)
    model = cal.fit_monotone(train)
    q10, q90 = quantile_model(train, 0.1), quantile_model(train, 0.9)
    p_cal, p_te = np.clip(model.predict(calib), 0, None), np.clip(model.predict(test), 0, None)
    b_cal, b_te = bandof(calib.age), bandof(test.age)
    s_all = calib.km.mean() / p_cal.mean()
    fb = {b: (calib.km[b_cal == b].mean() / p_cal[b_cal == b].mean() if (b_cal == b).sum() >= 30 else s_all) for b in BANDS}
    k = np.array([fb[b] for b in b_te])
    lk_age = {b: (calib.km[b_cal == b].mean() if (b_cal == b).sum() >= 30 else calib.km.mean()) for b in BANDS}
    lk_age_fuel = {}
    for b in BANDS:
        for f in FUEL_CATS:
            m = (b_cal == b) & (calib.fuel.to_numpy() == f)
            lk_age_fuel[(b, f)] = calib.km[m].mean() if m.sum() >= 30 else lk_age[b]
    preds = {
        "uncalibrated ML (trained on the other two markets)": p_te,
        "ML calibrated with age-band aggregates": p_te * k,
        "lookup: age-band means only (analogue of CBS by age)": np.array([lk_age[b] for b in b_te]),
        "lookup: age band x fuel means (analogue of CBS age + propulsion)": np.array([lk_age_fuel[(b, f)] for b, f in zip(b_te, test.fuel.to_numpy())]),
        "oracle: ML trained on the target market's individual vehicles": np.clip(cal.fit_monotone(calib).predict(test), 0, None),
    }
    y = test.km.to_numpy()
    for name, p in preds.items():
        rowsB.append({"target market": tgt, "method": name, **metrics(y, p)})
    lo, hi = np.minimum(q10.predict(test), q90.predict(test)) * k, np.maximum(q10.predict(test), q90.predict(test)) * k
    q = {b: (np.percentile(calib.km[b_cal == b], [10, 90]) if (b_cal == b).sum() >= 30 else np.percentile(calib.km, [10, 90])) for b in BANDS}
    llo, lhi = np.array([q[b][0] for b in b_te]), np.array([q[b][1] for b in b_te])
    rowsB.append({"target market": tgt, "method": "INTERVAL ML (quantile models x calibration factor)", "coverage": float(((y >= lo) & (y <= hi)).mean()), "median width km": float(np.median(hi - lo))})
    rowsB.append({"target market": tgt, "method": "INTERVAL lookup (age-band 10-90% of the aggregates' own vehicles)", "coverage": float(((y >= llo) & (y <= lhi)).mean()), "median width km": float(np.median(lhi - llo))})
    print(f"Part B: {tgt} done", flush=True)
OUT["B_leave_one_market_out"] = rowsB
(ROOT / "ml" / "model1_vs_cbs_results.json").write_text(json.dumps(OUT, indent=1), encoding="utf-8")
print("written ml/model1_vs_cbs_results.json", flush=True)
