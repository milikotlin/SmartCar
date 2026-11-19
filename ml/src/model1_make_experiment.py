"""READ-ONLY evidence for the final review: would the make (or make + model) personalise the Model 1 estimate?

Leave-one-market-out, exactly the protocol of model1_vs_cbs.py (train on two markets, calibrate with age-band aggregates of half of the target market, test on the other half),
comparing the production design (age + fuel) with age + fuel + make and age + fuel + make|model (most frequent categories as one-hot, the rest = "other").
Nothing is exported: this only decides whether Model 1 should change. Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_make_experiment.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbs_reference as cbs  # noqa: E402
import mileage_data as md  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FUELS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]
clean = {k: md.load_clean(k)[0] for k in md.LOADERS}
IN = pd.concat([clean["d8_in"], clean["d3_cardekho"]], ignore_index=True)
MARKETS = {"UK": clean["d7_uk"], "India": IN, "US": clean["d6_craigslist"]}
for df in MARKETS.values():
    df["make"] = df["make"].astype(str).str.strip().str.title()
    df["make_model"] = df["make"] + "|" + df["model"].astype(str).str.strip().str.title()
BANDS = cbs.BAND_LABELS
bandof = lambda s: s.map(cbs.age_to_band).to_numpy()


def design(df, make_levels, mm_levels):
    X = [df.age.to_numpy(dtype=float)] + [(df.fuel == f).to_numpy(dtype=float) for f in FUELS]
    X += [(df.make == m).to_numpy(dtype=float) for m in make_levels]
    X += [(df.make_model == m).to_numpy(dtype=float) for m in mm_levels]
    return np.column_stack(X)


def fit(train, use_make, use_mm):
    make_levels = list(train.make.value_counts().head(40).index) if use_make else []
    mm_levels = list(train.make_model.value_counts().head(100).index) if use_mm else []
    n_extra = len(FUELS) + len(make_levels) + len(mm_levels)
    est = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8, tree_method="hist", n_jobs=8, random_state=0, monotone_constraints=tuple([1] + [0] * n_extra))
    est.fit(design(train, make_levels, mm_levels), train.km)
    return lambda df: np.clip(est.predict(design(df, make_levels, mm_levels)), 0, None)


def rmse(y, p):
    return float(np.sqrt(np.mean((y - p) ** 2)))


rows = []
for tgt, data in MARKETS.items():
    data = data[data.fuel.isin(FUELS)]
    calib, test = train_test_split(data, test_size=0.5, random_state=0)
    train = pd.concat([MARKETS[m][MARKETS[m].fuel.isin(FUELS)] for m in MARKETS if m != tgt], ignore_index=True)
    shared = float(test.make.isin(set(train.make)).mean())
    b_cal, b_te = bandof(calib.age), bandof(test.age)
    res = {"target": tgt, "share_of_test_vehicles_whose_make_exists_in_training_markets": round(shared, 3)}
    for name, (um, umm) in {"age+fuel (production)": (False, False), "age+fuel+make": (True, False), "age+fuel+make|model": (True, True)}.items():
        f = fit(train, um, umm)
        p_cal, p_te = f(calib), f(test)
        s_all = calib.km.mean() / p_cal.mean()
        fb = {b: (calib.km[b_cal == b].mean() / p_cal[b_cal == b].mean() if (b_cal == b).sum() >= 30 else s_all) for b in BANDS}
        res[name] = round(rmse(test.km.to_numpy(), p_te * np.array([fb[b] for b in b_te])))
    rows.append(res)
    print(res, flush=True)
(ROOT / "ml" / "model1_make_experiment.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
