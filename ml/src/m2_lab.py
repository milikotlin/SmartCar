"""Shared pieces of the Model 2 experiments. Used by model2_train.py.

Training rows : Kaggle Dataset 1 (two original files; leaky Maintenance_Type and cost columns removed), enriched with Dataset 4; + SYNTHETIC vehicles generated from the FIT part of the
                official UK inspections (real outcome: a defect found at the next inspection). Electric / hybrid: Dataset 5 + the same generator.
Judged on     : REAL inspection outcomes of vehicles never used (UK val to choose, UK test and the Netherlands once).

Missing inputs are part of the problem, not an accident: an Israeli plate usually has no service log, no recorded inspection and no known odometer. Training rows are therefore MASKED at
random (days since service, failure history, measured odometer), so that the model learns what to say in each situation instead of reading "unknown" as "zero".
"""
import sys
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
from kaggle_sources import find  # noqa: E402
from official_data import nl_outcomes, outcome_pairs  # noqa: E402
from synthesis import SequentialCART, fidelity  # noqa: E402
from app.ml.spec_features import KM_BINS, M2_EV_EXTRA, M2_EV_FEATURES, M2_FEATURES, make_model_key  # noqa: E402

SEED = 42
ART = ROOT / "backend" / "app" / "ml" / "artifacts" / "spec"
D1_MAKE = {"Ford": "ford", "Chevy": "chevrolet", "Tesla": "tesla", "Volvo": "volvo", "MAN": "man", "Isuzu": "isuzu", "Scania": "scania", "Mercedes": "mercedes-benz"}
FLAG = 0.40              # operating point used for Recall / Precision: the 40% of vehicles with the highest score


@lru_cache(maxsize=1)
def model1():
    from app.ml.spec_mileage import SpecMileageModel
    return SpecMileageModel(ART.parent)


def model1_km(d: pd.DataFrame, age: str = "age_year", cc: str = "cc") -> np.ndarray:
    """Model 1 -> Model 2: the odometer Model 1 predicts for every row (its own scale, before the Israeli localisation)."""
    m = model1()
    X = pd.DataFrame({"age": d[age].clip(upper=m.data_age).astype(int), "engine_cc": pd.to_numeric(d[cc], errors="coerce"), "automatic": np.nan, "fuel": d.fuel, "owner_type": "Unknown",
                      "make_model": d.make_model, "listing": 0.0})
    X.loc[X.engine_cc <= 0, "engine_cc"] = np.nan
    X.loc[X.fuel == "electric", "engine_cc"] = 0.0
    return np.clip(m.pipeline.predict(X), 500, None)


def brand_index(fit: pd.DataFrame) -> dict:
    """Brand_Reliability_Index: 50 = average for its age; from the FIT vehicles only (so the judges stay independent), shrunk for small makes (300 pseudo-vehicles)."""
    exp = fit.age_year.map(fit.groupby("age_year").y.mean())
    g = pd.DataFrame({"m": fit.make.str.lower(), "o": fit.y.astype(float), "e": exp}).groupby("m").agg(n=("o", "size"), o=("o", "sum"), e=("e", "sum"))
    base = float(fit.y.mean())
    r = (g.o + 300 * base) / (g.e + 300 * base)
    idx = (50 / r).clip(0, 100).round(1)
    return {"method": "50 x (age-adjusted expected / observed) share of real UK vehicles with a defect at the next inspection; fitted on the FIT vehicles only, shrunk towards 50 for small makes",
            "default": 50.0, "index": {k: float(v) for k, v in idx.items()}, "vehicles": {k: int(v) for k, v in g.n.items()}}


def d4_rates() -> dict:
    d = pd.read_csv(find("d4_telemetry", "synthetic_telemetry_data.csv"))[["odometer_reading", "engine_failure_imminent", "brake_issue_imminent", "battery_issue_imminent"]]
    cols = list(d.columns[1:])
    d["bin"] = pd.cut(d.odometer_reading.astype(float), KM_BINS, right=False, labels=False)
    overall = {c: float(d[c].mean()) for c in cols}
    tab = {}
    for b in range(len(KM_BINS) - 1):
        s = d[d.bin == b]
        tab[str(b)] = {c: float((s[c].sum() + 50 * overall[c]) / (len(s) + 50)) for c in cols} | {"rows": int(len(s))}
    # the first group has 168 rows: raw, its brake and battery rates were above the next group's, so the model raised the risk of brand-new cars. Non-decreasing (isotonic) rates, weighted by rows.
    bins = sorted(tab, key=int)
    for c in cols:
        smooth = IsotonicRegression(increasing=True).fit_transform(np.arange(len(bins)), [tab[b][c] for b in bins], sample_weight=[tab[b]["rows"] + 50 for b in bins])
        for b, v in zip(bins, smooth):
            tab[b][c] = float(v)
    return {"bins_km": [float(x) for x in KM_BINS[:-1]], "overall": overall, "by_bin": tab,
            "note": "Dataset 4 has no age column: grouped by mileage, shrunk towards the overall rate (50 pseudo-rows), non-decreasing with mileage (isotonic)"}


def d4_cols(km, d4):
    b = pd.cut(pd.Series(np.asarray(km, float)), KM_BINS, right=False, labels=False).fillna(0).astype(int).astype(str)
    return {f"d4_{n}_fault_rate": b.map({k: v[c] for k, v in d4["by_bin"].items()}).to_numpy(float) for n, c in (("engine", "engine_failure_imminent"), ("brake", "brake_issue_imminent"), ("battery", "battery_issue_imminent"))}


def features(age, km, measured, days, history, brand, d4, **extra) -> pd.DataFrame:
    n = len(age)
    f = pd.DataFrame({"vehicle_age": np.asarray(age, float), "km": np.asarray(km, float), "km_measured": np.asarray(measured, float), "days_since_last_maintenance": np.asarray(days, float),
                      "failure_history": np.minimum(np.asarray(history, float), 2.0), "brand_reliability_index": np.asarray(brand, float), **d4_cols(km, d4)})
    for c in M2_EV_EXTRA:
        f[c] = np.asarray(extra.get(c, np.full(n, np.nan)), float)
    return f


# ------------------------------------------------------------------ Kaggle
def load_d1(bri, d4) -> pd.DataFrame:
    out = []
    for name, file in (("d1_92k", "logistics_dataset_with_maintenance_required.csv"), ("d1_v2_250k", "logistics_predictive_maintenanceV2.csv")):
        d = pd.read_csv(find("d1_logistics", file))
        dt = pd.to_datetime(d.Last_Maintenance_Date)
        days = d.Days_Since_Last_Maintenance if "Days_Since_Last_Maintenance" in d else (dt.max() + pd.Timedelta(days=1) - dt).dt.days
        mk = d.Make_and_Model.str.split().str[0].map(D1_MAKE)
        out.append(pd.DataFrame({"file": name, "make": mk, "age_year": (dt.max().year - d.Year_of_Manufacture).clip(lower=0), "days": days.astype(float), "fh": d.Failure_History.astype(float),
                                 "fuel": np.where(mk == "tesla", "electric", "diesel"), "y": d.Maintenance_Required.astype(int)}))
    D = pd.concat(out, ignore_index=True)
    D["make_model"], D["cc"] = [make_model_key(m, "") for m in D.make], np.nan
    combo = D[["age_year", "fuel", "make_model", "cc"]].drop_duplicates(["age_year", "fuel", "make_model"])
    combo["km"] = model1_km(combo)
    D = D.merge(combo.drop(columns="cc"), on=["age_year", "fuel", "make_model"], how="left")
    D["brand"] = D.make.map(bri["index"]).fillna(50.0)
    return D


def load_d5() -> pd.DataFrame:
    d = pd.read_csv(find("d5_nev", "Fault_nev_dataset.csv"))
    return d.assign(y=(d.fault_type != "no_fault").astype(int))[["last_service_distance", "service_frequency", "time_since_last_fault", "driving_distance", "y"]]


# ------------------------------------------------------------------ synthetic vehicles from official inspections
ORDER = ["fuel", "age_year", "make_model", "cc", "km", "any_defect", "y"]


def synth_official(fit: pd.DataFrame, n: int, seed: int = 7) -> pd.DataFrame:
    real = fit.assign(any_defect=fit.any_defect.astype(str), y=fit.y.astype(str))[ORDER]
    g = SequentialCART(ORDER, ["fuel", "make_model", "any_defect", "y"], ["km"], min_leaf=60).fit(real.assign(y=real.y.astype(int)).assign(y=lambda d: d.y))
    s = g.sample(n, seed=seed)
    s["y"], s["any_defect"] = s.y.astype(int), s.any_defect.astype(int)
    names = fit.drop_duplicates("make_model").set_index("make_model").make
    s["make"], s["age_year"], s["km"] = s.make_model.map(names), s.age_year.round().astype(int), s.km.clip(100, 500_000)
    return s


# ------------------------------------------------------------------ real scenarios (what the API knows about a vehicle)
SCENARIOS = {"no records (plate only)": (False, False), "odometer known": (True, False), "last inspection known": (False, True), "odometer + last inspection": (True, True)}


def scenario(d: pd.DataFrame, bri, d4, odo: bool, hist: bool, days=None) -> pd.DataFrame:
    n = len(d)
    brand = d.make.str.lower().map(bri["index"]).fillna(50.0)
    return features(d.age_year, d.km if odo else d.km_model1, np.full(n, float(odo)), np.full(n, np.nan) if days is None else days, d.any_defect if hist else np.full(n, np.nan), brand, d4)


def judge(y, p) -> dict:
    y, p = np.asarray(y), np.asarray(p, float)
    k = int(round(len(p) * FLAG))
    top = np.argsort(-(p + np.random.default_rng(0).random(len(p)) * 1e-9))[:k]
    hit = y[top].sum()
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "recall": float(hit / y.sum()), "precision": float(hit / k), "base_rate": float(y.mean()), "n": int(len(y))}


def within_age_auc(d, p) -> float:
    num = den = 0.0
    for _, i in d.groupby("age_year").indices.items():
        yy = d.y.to_numpy()[i]
        if len(i) > 200 and 0 < yy.mean() < 1:
            num += roc_auc_score(yy, np.asarray(p)[i]) * len(i)
            den += len(i)
    return float(num / den)
