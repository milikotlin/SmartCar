"""Calibration of Model 1 against official aggregate statistics (experiments only; nothing exported).

Idea: the learned regression gives the SHAPE of odometer-vs-age and relative effects (fuel...), trained on used-car listings of other
countries. Official Israeli aggregates (CBS) give the LEVEL. We rescale the model's yearly increments, per age band / ownership / fuel,
so that the model's implied POPULATION means on the Israeli registry match the CBS means. This corrects bias of the average;
it cannot, by construction, tell anything about the spread of individual vehicles around that average.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbs_reference as cbs  # noqa: E402
import mileage_experiments as mx  # noqa: E402

MAX_AGE = 45
FUEL_ALIAS = {"electric": "petrol"}   # only ~12 EV rows in the training data: use the petrol age curve (NOT validated; CBS has no EV data)


def fit_monotone(train: pd.DataFrame, algo: str = "xgb", **cfg):
    """Age->odometer model forced to be non-decreasing in age (no negative yearly increments)."""
    cfg = {"numeric": ["age"], "low_card": ["fuel"], "make_enc": None, **cfg}
    pipe = mx.build_pipeline(algo=algo, **cfg)
    prep = pipe.named_steps["prep"].fit(train, train.km)
    n = prep.transform(train.head(2)).shape[1]
    pipe.set_params(est__monotone_constraints=tuple([1] + [0] * (n - 1)))   # first feature = age
    return pipe.fit(train, train.km)


def _grid(fuel: str) -> pd.DataFrame:
    return pd.DataFrame({"age": np.arange(0, MAX_AGE + 1), "fuel": fuel, "make": "unknown", "make_model": "unknown",
                         "model": "unknown", "transmission": np.nan, "engine_cc": np.nan})


def cumulative_curves(model, fuels) -> dict:
    """fuel -> predicted cumulative odometer (km) for ages 0..MAX_AGE (kept non-decreasing)."""
    return {f: np.maximum.accumulate(np.clip(model.predict(_grid(f)), 0, None)) for f in fuels}


def increments(curve: np.ndarray, a_sup: int = None, rates_km: np.ndarray = None) -> np.ndarray:
    """Yearly increments: inc[0] = km at age 0; inc[a] = odo(a) - odo(a-1).

    Support-aware hybrid: for ages above `a_sup` (where the training data has too few vehicles, so the learned curve is flat)
    the learned increment is replaced by the official CBS yearly rate `rates_km[a]`.
    """
    inc = np.r_[curve[0], np.diff(curve)]
    if a_sup is not None and rates_km is not None:
        inc = inc.copy()
        inc[a_sup + 1:] = rates_km[a_sup + 1:]
    return inc


def supported_max_age(train_ages: pd.Series, min_rows: int = 300) -> int:
    """Largest age such that every age <= it has at least `min_rows` training vehicles."""
    counts = train_ages.round().astype(int).value_counts()
    a = 0
    while counts.get(a + 1, 0) >= min_rows:
        a += 1
    return a


def implied_annual(curves: dict, fuel: pd.Series, age: pd.Series, a_sup: int = None, rates_km: np.ndarray = None) -> np.ndarray:
    out = np.zeros(len(age))
    f_arr, a_arr = fuel.to_numpy(), age.to_numpy().astype(int).clip(0, MAX_AGE)
    for f in np.unique(f_arr):
        inc = increments(curves[FUEL_ALIAS.get(f, f)], a_sup, rates_km)
        m = f_arr == f
        out[m] = inc[a_arr[m]]
    return out


def rake_means(base: np.ndarray, groups: dict, targets: dict, families: list, n_iter: int = 500, tol: float = 1e-10):
    """Multiplicative factors per category so that the mean of base*factors in each category equals the official mean.

    groups: {family: category per vehicle}; targets: {family: {category: official mean}}; families: which ones to use.
    """
    factors = {fam: {c: 1.0 for c in targets[fam]} for fam in families}
    mult = np.ones(len(base))
    for _ in range(n_iter):
        worst = 0.0
        for fam in families:
            g = np.asarray(groups[fam])
            for cat, tgt in targets[fam].items():
                mask = g == cat
                if not mask.any():
                    continue
                f = tgt / (base[mask] * mult[mask]).mean()
                mult[mask] *= f
                factors[fam][cat] *= f
                worst = max(worst, abs(f - 1))
        if worst < tol:
            break
    # Gauge freedom: scaling every age factor by c and dividing every ownership factor by c leaves the product unchanged.
    # Fix it by making the vehicle-weighted geometric mean of the ownership factors equal to 1 (scale moves to the age factors).
    if "age" in factors and "own" in factors:
        own = np.asarray(groups["own"])
        logs = np.array([np.log(factors["own"].get(o, 1.0)) for o in own])
        g = float(np.exp(logs.mean()))
        factors["own"] = {k: v / g for k, v in factors["own"].items()}
        factors["age"] = {k: v * g for k, v in factors["age"].items()}
    # Categories with no vehicle in the registry sample were never fitted: inherit the factor of the previous (younger) band.
    for fam in factors:
        present = set(np.asarray(groups[fam]).tolist())
        prev = None
        for cat in targets[fam]:
            if cat in present:
                prev = factors[fam][cat]
            elif prev is not None:
                factors[fam][cat] = prev
    return factors, mult


def calibrated_odometer(curves: dict, factors: dict, fuel, age, ownership=None, fuel_cbs=None, a_sup: int = None, rates_km: np.ndarray = None) -> np.ndarray:
    """Calibrated cumulative odometer: sum of calibrated yearly increments."""
    fuel, age = np.asarray(fuel), np.asarray(age).astype(int).clip(0, MAX_AGE)
    f_age_tbl = factors.get("age", {})
    f_age = np.array([f_age_tbl.get(cbs.age_to_band(a), 1.0) for a in range(MAX_AGE + 1)])
    out = np.zeros(len(age))
    for f in np.unique(fuel):
        cal_cum = np.cumsum(increments(curves[FUEL_ALIAS.get(f, f)], a_sup, rates_km) * f_age)
        m = fuel == f
        out[m] = cal_cum[age[m]]
    if ownership is not None:
        out = out * np.array([factors.get("own", {}).get(o, 1.0) for o in ownership])
    if fuel_cbs is not None:
        out = out * np.array([factors.get("fuel", {}).get(f, 1.0) if f is not None else 1.0 for f in fuel_cbs])
    return out


def cbs_cumulative_expected(rates_by_band: dict) -> np.ndarray:
    """Expected odometer by age implied by CBS yearly rates alone: sum_{a<=age} rate(band(a)) (stationarity assumed)."""
    rates = np.array([rates_by_band[cbs.age_to_band(a)] * 1000 for a in range(MAX_AGE + 1)])
    return np.cumsum(rates)
