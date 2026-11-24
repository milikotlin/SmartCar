"""Model 1 (Smart_Car_Models.pdf): odometer regression on Kaggle Datasets 7 + 8 + 3, augmented with synthetic vehicles generated from official odometers
(UK MOT), XGBoost chosen by RMSE / MAE. Trained by ml/src/model1_train.py; this module only predicts.

From the model to an Israeli estimate (all numbers in model1_calibration.json):
  * LEVEL  - official: CBS kilometres per year by age, with raked factors for age band, ownership and propulsion (CBS Publication 1923);
  * SHAPE  - learned: how the yearly use of a fuel type evolves with age (real odometers), and what make / model / engine add for this vehicle. The second part
             is shrunk (`lambda`), because it did not hold in either of the two foreign markets it was tested on (India, US): see ml/model1_transfer_shrinkage.json.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.mileage import MAX_PLAUSIBLE_ANNUAL_KM, MileageEstimate
from app.ml.spec_features import M1_FEATURES


def _band(age: int, bands: list[list[int]], labels: list[str]) -> str:
    for (lo, hi), label in zip(bands, labels):
        if lo <= age <= hi:
            return label
    return labels[-1]


def is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v))


class SpecMileageModel:
    def __init__(self, artifact_dir: Path, calibration: dict | None = None):
        d = Path(artifact_dir) / "spec"
        self.pipeline = joblib.load(d / "model1_pipeline.joblib")
        self.cal = calibration if calibration is not None else json.loads((d / "model1_calibration.json").read_text(encoding="utf-8"))
        self.card = json.loads((d / "model1_card.json").read_text(encoding="utf-8")) if (d / "model1_card.json").exists() else {}
        c = self.cal
        self.max_age, self.data_age = int(c["max_age"]), int(c["data_max_age"])
        self.rates = np.array(c["rates_km_by_age"], dtype=float)
        f_age = np.array([c["age_band_factors"].get(_band(a, c["age_bands"], c["age_band_labels"]), 1.0) for a in range(self.max_age + 1)])
        yearly = self.rates * f_age
        self.official_cum = np.r_[0.4 * yearly[0], np.cumsum(yearly)[:-1]]            # kilometres after `a` calendar years; a car of the current year: part of a year
        self.af = {f: np.array(v, dtype=float) for f, v in c["age_fuel_mean"].items()}  # learned mean odometer by fuel and age
        self.shape = {f: np.array(v, dtype=float) for f, v in c["age_fuel_shape"].items()}  # ... relative to the average Israeli vehicle of that age
        self.f_own, self.f_fuel, self.own_map = c["ownership_factors"], c["fuel_factors"], c["registry_ownership_to_cbs"]
        self.lam = float(c["lambda"])
        self._cache: dict = {}

    def frame(self, features: dict, ages) -> pd.DataFrame:
        df = pd.DataFrame([{**{k: features.get(k) for k in M1_FEATURES}, "age": int(a)} for a in ages], columns=M1_FEATURES)
        for c in ("engine_cc", "automatic"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df["engine_cc"] <= 0, "engine_cc"] = np.nan
        df.loc[df["fuel"] == "electric", "engine_cc"] = 0.0
        df["listing"] = 0.0                                                            # a vehicle in use, not a used-car listing
        return df

    def fill_missing(self, features: dict) -> dict:
        """Engine size / transmission unknown -> the model's KNN imputer (K=5), once, at the vehicle's real age."""
        f = dict(features)
        if is_missing(f.get("automatic")) or (is_missing(f.get("engine_cc")) and f.get("fuel") != "electric"):
            row = self.frame(f, [min(int(f.get("age") or 0), self.data_age)])
            imputer = self.pipeline.named_steps["prep"].named_transformers_["numeric"].named_steps["impute"]
            filled = imputer.transform(row[["age", "engine_cc", "automatic", "fuel"]])[0]
            f["engine_cc"], f["automatic"] = float(filled[1]), float(filled[2])
        return f

    def learned(self, features: dict) -> float:
        """The regression's own output for this vehicle (kilometres, before anything Israeli)."""
        f = self.fill_missing(features)
        key = tuple(sorted((k, str(v)) for k, v in f.items()))
        if key not in self._cache:
            if len(self._cache) > 5000:
                self._cache.clear()
            a = min(max(int(f.get("age") or 0), 0), self.data_age)
            self._cache[key] = float(np.clip(self.pipeline.predict(self.frame(f, [a]))[0], 0, None))
        return self._cache[key]

    def model2_km(self, features: dict, km: float | None = None, estimated_km: float | None = None) -> float:
        """Model 1 -> Model 2. Model 2 was trained with the odometer Model 1 predicts on its own scale (transmission and owners unknown there, as in the inspections).
        A known odometer is expressed on that scale through its ratio to the Israeli estimate: "30% more than expected here" stays "30% more than expected"."""
        base = self.learned({**features, "automatic": None, "owner_type": "Unknown"})
        return base if not km or not estimated_km else base * float(np.clip(km / estimated_km, 0.1, 5.0))

    def localise(self, fuel: str, own_cbs: str | None, age: int, ratio: float) -> float:
        fuel = fuel if fuel in self.shape else "petrol"
        a = min(max(age, 0), self.max_age)
        path = self.official_cum[: a + 1] * self.shape[fuel][np.minimum(np.arange(a + 1), self.data_age)]
        level = self.f_own.get(own_cbs, 1.0) * self.f_fuel.get(fuel, self.f_fuel["petrol"])
        return float(np.maximum.accumulate(path)[-1] * level * float(np.clip(ratio, 0.5, 2.0)) ** self.lam)

    def individual_ratio(self, features: dict, learned: float) -> float:
        fuel = features.get("fuel") if features.get("fuel") in self.af else "petrol"
        a = min(max(int(features.get("age") or 0), 0), self.data_age)
        return learned / max(self.af[fuel][a], 1000.0)

    def estimate(self, features: dict, ownership: str | None) -> MileageEstimate:
        notes = []
        age, fuel = int(features.get("age") or 0), features.get("fuel")
        a = min(max(age, 0), self.max_age)
        if age > self.max_age:
            notes.append(f"age above {self.max_age}: capped")
        own = self.own_map.get(ownership or "")
        if own is None:
            notes.append("ownership not in the official statistics: average factor used")
        raw = self.learned(features)
        est = self.localise(fuel, own, a, self.individual_ratio(features, raw))
        key = f"{fuel if fuel in self.cal['interval_ratio_quantiles'] else 'petrol'}"
        q = self.cal["interval_ratio_quantiles"][key]
        lo_q, hi_q = q.get(_band(a, self.cal["age_bands"], self.cal["age_band_labels"]), q["all"])
        if a > self.data_age:
            notes.append(f"age above {self.data_age}: beyond the training data, official yearly rates continue")
        missing = [n for n, k in (("engine size", "engine_cc"), ("transmission", "automatic")) if is_missing(features.get(k)) and not (k == "engine_cc" and fuel == "electric")]
        if missing:
            notes.append(f"{' and '.join(missing)} not found in the official model data: filled by the KNN imputer (K=5) from similar vehicles")
        reliability, reason = "ok", None
        support = self.cal["real_vehicles_by_fuel_age"].get(fuel, [])
        n = support[min(a, len(support) - 1)] if support else 0
        if fuel == "electric":
            reliability, reason = "low", "no official Israeli statistics exist for electric vehicles: the estimate rests on UK electric odometers"
        elif fuel not in self.shape:
            reliability, reason = "low", "unknown fuel type: the petrol curve is used"
        elif a > self.cal.get("support_max_age", {}).get(fuel, 999):
            reliability, reason = "low", f"older than {self.cal['support_max_age'][fuel]} years: the real {fuel} vehicles of this age are mostly former taxis, so the official average curve continues"
        elif n < self.cal["min_real_vehicles"] and 1 <= a <= self.data_age:
            label = "LPG/CNG" if fuel == "lpg_cng" else fuel
            reliability, reason = "low", f"too few real {label} vehicles of this age ({n}) support the estimate"
        annual = est / max(a, 1)
        if reliability == "ok" and a > 0 and annual > MAX_PLAUSIBLE_ANNUAL_KM:
            est = float(self.official_cum[a] * self.f_own.get(own, 1.0))
            reliability, reason = "low", f"the model implies about {int(round(annual, -3)):,} km per year, above every official group average: the official average for this age and ownership is shown instead"
            annual = est / max(a, 1)
        return MileageEstimate(km=int(round(est, -2)), km_low=int(round(min(est * lo_q, est), -2)), km_high=int(round(max(est * hi_q, est), -2)), annual_km=int(round(annual, -2)),
                               notes=tuple(notes), reliability=reliability, reliability_reason=reason, raw_km=int(round(raw, -2)))
