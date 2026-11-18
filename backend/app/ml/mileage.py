"""Model 1 inference: calibrated odometer estimate with an indicative uncertainty range (Stage 1 of the pipeline).

The learned part is XGBoost (age + fuel, monotone in age; plus 10% / 90% quantile models). The calibration to the official Israeli level
(CBS Publication 1923, age band x ownership) is a fixed set of factors computed offline by ml/src/final_model1.py.
Everything the API needs is loaded once at start-up from backend/app/ml/artifacts/model1/.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xgboost as xgb

FUEL_COLUMNS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]      # feature order used in training: [age, one-hot fuel...]


@dataclass(frozen=True)
class MileageEstimate:
    km: int
    km_low: int
    km_high: int
    annual_km: int
    notes: tuple[str, ...]


def _age_band(age: int, bands: list[list[int]], labels: list[str]) -> str:
    for (lo, hi), label in zip(bands, labels):
        if lo <= age <= hi:
            return label
    return labels[-1]


class MileageModel:
    def __init__(self, artifact_dir: Path):
        d = Path(artifact_dir) / "model1"
        self.card = json.loads((d / "model1_card.json").read_text(encoding="utf-8"))
        self.cal = json.loads((d / "calibration.json").read_text(encoding="utf-8"))
        self.max_age = int(self.cal["max_age"])
        self.a_sup = int(self.cal["a_sup"])
        self.rates_km = np.array(self.cal["rates_km_by_age"], dtype=float)
        self.alias = self.cal["fuel_alias"]
        boosters = {}
        for name in ("mean", "q10", "q90"):
            b = xgb.Booster()
            b.load_model(str(d / f"{name}_model.json"))
            boosters[name] = b
        # learned curves for every fuel and age (the models only take age and fuel, so the grid is the whole model)
        self.mean_raw, self.q10, self.q90 = {}, {}, {}
        for fuel in FUEL_COLUMNS:
            x = np.zeros((self.max_age + 1, 1 + len(FUEL_COLUMNS)), dtype=np.float32)
            x[:, 0] = np.arange(self.max_age + 1)
            x[:, 1 + FUEL_COLUMNS.index(fuel)] = 1.0
            dm = xgb.DMatrix(x)
            self.mean_raw[fuel] = np.clip(boosters["mean"].predict(dm), 0, None)
            self.q10[fuel] = np.clip(boosters["q10"].predict(dm), 0, None)
            self.q90[fuel] = np.clip(boosters["q90"].predict(dm), 0, None)
        self.curve = {f: np.maximum.accumulate(c) for f, c in self.mean_raw.items()}          # cumulative, non-decreasing
        f_band = self.cal["age_band_factors"]
        self.f_age = np.array([f_band[_age_band(a, self.cal["age_bands"], self.cal["age_band_labels"])] for a in range(self.max_age + 1)])
        self.f_own = self.cal["ownership_factors"]
        self.own_map = self.cal["registry_ownership_to_cbs"]
        self._calibrated: dict[str, np.ndarray] = {}

    def _calibrated_curve(self, fuel: str) -> np.ndarray:
        if fuel not in self._calibrated:
            curve = self.curve[fuel]
            inc = np.r_[curve[0], np.diff(curve)]
            inc[self.a_sup + 1:] = self.rates_km[self.a_sup + 1:]     # above the supported age the learned curve is flat: use the official yearly rate
            self._calibrated[fuel] = np.cumsum(inc * self.f_age)
        return self._calibrated[fuel]

    def estimate(self, fuel: str, age: int, ownership: str | None) -> MileageEstimate:
        """fuel in {petrol, diesel, hybrid, electric, lpg_cng}; ownership in registry vocabulary {private, leasing, company, dealer, rental} or None."""
        notes = []
        fuel_key = self.alias.get(fuel, fuel)
        if fuel_key not in self.curve:
            fuel_key = "petrol"
            notes.append("unknown fuel type: petrol curve used")
        if fuel == "electric":
            notes.append("electric vehicle: petrol curve used (no official or training data for electric vehicles)")
        a = int(min(max(age, 0), self.max_age))
        if age > self.max_age:
            notes.append(f"age above {self.max_age}: capped")
        cbs_own = self.own_map.get(ownership or "", None)
        factor = self.f_own.get(cbs_own, 1.0) if cbs_own else 1.0
        if cbs_own is None:
            notes.append("ownership not in the official statistics: average factor used")
        est = float(self._calibrated_curve(fuel_key)[a] * factor)
        learned = max(float(self.curve[fuel_key][a]), 1000.0)
        ratio = est / learned                                    # same scaling the point estimate received
        lo, hi = float(self.q10[fuel_key][a] * ratio), float(self.q90[fuel_key][a] * ratio)
        lo, hi = min(lo, est), max(hi, est)
        if a > self.a_sup:
            notes.append(f"age above {self.a_sup}: the training data carry no information; official yearly rates were used")
        annual = est / max(a, 1) if a > 0 else est
        return MileageEstimate(km=int(round(est, -2)), km_low=int(round(lo, -2)), km_high=int(round(hi, -2)), annual_km=int(round(annual, -2)), notes=tuple(notes))
