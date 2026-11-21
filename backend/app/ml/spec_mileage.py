"""Model 1 built as Smart_Car_Models.pdf specifies (Datasets 7 + 8 + 3 from Kaggle; OHE + Target/Frequency encoding experiment; KNN imputer K=5;
Linear/Ridge vs Random Forest / XGBoost, chosen by RMSE and MAE). Trained offline by ml/src/spec_model1.py; this module only predicts.

Added on top of the specified model (documented in docs/MODEL_CARDS.md, not part of the PDF): the CBS calibration to the official Israeli level
(age band x ownership), an indicative 80% range from held-out residuals, and the "low reliability" flags where the training data cannot support a figure.

The model gives the odometer of a vehicle as a function of its features. For one vehicle the API predicts the whole age path (0..age) with the vehicle's
other features fixed; the yearly increments of that path are what the CBS factors calibrate (the CBS publishes yearly kilometres by age band).
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.mileage import MAX_PLAUSIBLE_ANNUAL_KM, MileageEstimate, smooth_cumulative
from app.ml.spec_features import M1_FEATURES


def _band(age: int, bands: list[list[int]], labels: list[str]) -> str:
    for (lo, hi), label in zip(bands, labels):
        if lo <= age <= hi:
            return label
    return labels[-1]


class SpecMileageModel:
    def __init__(self, artifact_dir: Path, calibration: dict | None = None):
        d = Path(artifact_dir) / "spec"
        self.pipeline = joblib.load(d / "model1_pipeline.joblib")
        self.cal = calibration if calibration is not None else json.loads((d / "model1_calibration.json").read_text(encoding="utf-8"))
        self.card = json.loads((d / "model1_card.json").read_text(encoding="utf-8")) if (d / "model1_card.json").exists() else {}
        c = self.cal
        self.max_age, self.a_sup, self.window = int(c["max_age"]), int(c["a_sup"]), int(c.get("smoothing_window", 3))
        self.rates_km = np.array(c["rates_km_by_age"], dtype=float)
        self.support = {k: int(v) for k, v in c.get("support_max_age", {}).items()}
        self.f_age = np.array([c["age_band_factors"].get(_band(a, c["age_bands"], c["age_band_labels"]), 1.0) for a in range(self.max_age + 1)])
        self.f_own, self.own_map = c["ownership_factors"], c["registry_ownership_to_cbs"]
        self.ratio_q = c.get("residual_ratio_quantiles", {})          # age band -> [q10, q90] of actual / predicted on held-out vehicles
        self._cache: dict = {}

    # ------------------------------------------------------------------ the learned path
    def frame(self, features: dict, ages) -> pd.DataFrame:
        rows = [{**{k: features.get(k) for k in M1_FEATURES}, "age": int(a)} for a in ages]
        df = pd.DataFrame(rows, columns=M1_FEATURES)
        for c in ("engine_cc", "automatic"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df["engine_cc"] <= 0, "engine_cc"] = np.nan
        return df

    def fill_missing(self, features: dict) -> dict:
        """Engine size / transmission unknown -> the model's own KNN imputer (K=5), applied ONCE at the vehicle's real age and then kept fixed along the age
        path (imputing at every age would give the same car a different engine at each age)."""
        f = dict(features)
        row = self.frame(f, [int(f.get("age") or 0)])
        if row[["engine_cc", "automatic"]].isna().any(axis=None):
            imputer = self.pipeline.named_steps["prep"].named_transformers_["numeric"].named_steps["impute"]
            filled = imputer.transform(row[["age", "engine_cc", "automatic"]])[0]
            f["engine_cc"], f["automatic"] = float(filled[1]), float(filled[2])
        return f

    def learned_path(self, features: dict) -> np.ndarray:
        """Cumulative odometer for ages 0..max_age (raw model output, monotone). Fuels without enough training vehicles at an age continue with the
        yearly growth of the same vehicle as a petrol car above their last supported age."""
        features = self.fill_missing(features)
        key = tuple(sorted((k, v) for k, v in features.items() if k != "age"))
        if key in self._cache:
            return self._cache[key]
        ages = range(self.max_age + 1)
        path = np.maximum.accumulate(np.clip(self.pipeline.predict(self.frame(features, ages)), 0, None))
        fuel = features.get("fuel")
        a_max = self.support.get(fuel)
        if a_max is not None and a_max < self.max_age:
            petrol = np.maximum.accumulate(np.clip(self.pipeline.predict(self.frame({**features, "fuel": "petrol"}, ages)), 0, None))
            path = path.copy()
            path[a_max + 1:] = path[a_max] + (petrol[a_max + 1:] - petrol[a_max])
        if len(self._cache) > 5000:
            self._cache.clear()
        self._cache[key] = path
        return path

    def calibrated_increments(self, features: dict) -> np.ndarray:
        path = smooth_cumulative(self.learned_path(features), self.a_sup, self.window)
        inc = np.r_[path[0], np.diff(path)]
        inc[self.a_sup + 1:] = self.rates_km[self.a_sup + 1:]           # above the supported age the training data carry no information
        return inc

    # ------------------------------------------------------------------ the estimate shown to the user
    def estimate(self, features: dict, ownership: str | None) -> MileageEstimate:
        notes = []
        age = int(features.get("age") or 0)
        a = min(max(age, 0), self.max_age)
        if age > self.max_age:
            notes.append(f"age above {self.max_age}: capped")
        cbs_own = self.own_map.get(ownership or "")
        factor = self.f_own.get(cbs_own, 1.0) if cbs_own else 1.0
        if cbs_own is None:
            notes.append("ownership not in the official statistics: average factor used")
        inc = self.calibrated_increments(features)
        est = float(np.cumsum(inc * self.f_age)[a] * factor)
        raw = float(self.learned_path(features)[a])
        band = _band(a, self.cal["age_bands"], self.cal["age_band_labels"])
        q10, q90 = self.ratio_q.get(band, [0.5, 1.6])
        lo, hi = min(est * q10, est), max(est * q90, est)
        if a > self.a_sup:
            notes.append(f"age above {self.a_sup}: the training data carry no information; official yearly rates were used")
        missing = [n for n, k in (("engine size", "engine_cc"), ("transmission", "automatic")) if features.get(k) is None or (isinstance(features.get(k), float) and np.isnan(features.get(k)))]
        if missing:
            notes.append(f"{' and '.join(missing)} not found in the official model data: filled by the KNN imputer (K=5) from similar vehicles")
        reliability, reason = "ok", None
        fuel = features.get("fuel")
        if fuel == "electric":
            reliability, reason = "low", "almost no training data exist for electric vehicles"
        elif fuel in self.support and a > self.support[fuel]:
            label = "LPG/CNG" if fuel == "lpg_cng" else fuel
            reliability, reason = "low", (f"the training data hold too few {label} vehicles older than {self.support[fuel]} years "
                                          "(under 30 per year of age): from there on the yearly growth of petrol vehicles was used")
        annual = est / max(a, 1)
        if a > 0 and annual > MAX_PLAUSIBLE_ANNUAL_KM:
            # The model + calibration give more than any official group average for this combination: show the OFFICIAL average for this age and
            # ownership instead (CBS yearly rates by age band x the ownership mean / fleet mean), flagged. The model's own figure stays in raw_km.
            own_mean = self.cal.get("cbs_ownership_all_thousand_km", {}).get(cbs_own or "", self.cal.get("cbs_fleet_mean_thousand_km", 15.2))
            cbs_est = float(self.rates_km[1: a + 1].sum() * own_mean / self.cal.get("cbs_fleet_mean_thousand_km", 15.2))
            model_annual = annual
            est, annual = cbs_est, cbs_est / a
            lo, hi = min(est * q10, est), max(est * q90, est)
            reliability, reason = "low", (f"Model 1 gave about {int(round(model_annual, -3)):,} km per year for this combination of age, fuel, ownership and car, more than "
                                          "any official group average (highest 28,400 km, leasing cars): the official average for this age and ownership is shown instead")
        out = MileageEstimate(km=int(round(est, -2)), km_low=int(round(lo, -2)), km_high=int(round(hi, -2)), annual_km=int(round(annual, -2)), notes=tuple(notes),
                              reliability=reliability, reliability_reason=reason, raw_km=int(round(raw, -2)))
        return out
