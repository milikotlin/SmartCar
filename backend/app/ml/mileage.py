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

# The highest yearly mileage the official statistics publish for any group is 28,400 km (leasing cars, CBS Publication 1923, Table 8). A calibrated estimate that implies
# more than 40,000 km per year comes from multiplying age, fuel and ownership effects that the CBS does not publish jointly: it is shown, but flagged low reliability.
MAX_PLAUSIBLE_ANNUAL_KM = 40_000

FUEL_COLUMNS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]      # feature order used in training: [age, one-hot fuel...]


@dataclass(frozen=True)
class MileageEstimate:
    km: int
    km_low: int
    km_high: int
    annual_km: int
    notes: tuple[str, ...]
    reliability: str = "ok"                   # ok | low: "low" when the training data do not support this fuel type at this age
    reliability_reason: str | None = None


def smooth_cumulative(curve: np.ndarray, a_sup: int, window: int) -> np.ndarray:
    """Smooth a cumulative-by-age curve through its yearly increments (centred moving average over `window` years, ages 1..a_sup).

    The learned curve is a tree model, so its yearly increments are steps (one year with almost no km, the next with a jump). The total at a_sup and
    everything above it are kept; only the way the kilometres are spread over the years changes. window <= 1 leaves the curve untouched.
    """
    c = np.asarray(curve, dtype=float)
    if window <= 1 or a_sup < 2:
        return c
    inc = np.diff(c[: a_sup + 1])
    half = window // 2
    sm = np.array([inc[max(0, i - half): i + half + 1].mean() for i in range(len(inc))])
    if abs(sm.sum()) > 1e-9:
        sm = sm * (inc.sum() / sm.sum())
    out = c.copy()
    out[1: a_sup + 1] = c[0] + np.cumsum(sm)
    out[a_sup + 1:] = out[a_sup] + (c[a_sup + 1:] - c[a_sup])
    return out


def apply_support(curves: dict, support_max_age: dict, fallback: str = "petrol") -> dict:
    """Where the training data hold too few vehicles of a fuel type at an age, continue that fuel's curve with the yearly growth of the petrol curve.

    support_max_age[fuel] = last age with enough training vehicles of that fuel (>= 30 per year of age). Up to there the curve is the fuel's own; above it only the
    level reached at that age is kept and the yearly increments of the fallback curve are added. Fuels without an entry are untouched.
    """
    out = {f: np.asarray(c, dtype=float).copy() for f, c in curves.items()}
    fb = np.asarray(curves[fallback], dtype=float)
    for fuel, a_max in support_max_age.items():
        if fuel == fallback or fuel not in out or a_max >= len(fb) - 1:
            continue
        out[fuel][a_max + 1:] = out[fuel][a_max] + (fb[a_max + 1:] - fb[a_max])
    return out


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
        self.support_max_age = {k: int(v) for k, v in self.cal.get("support_max_age", {}).items()}     # fuel -> last age with >= 30 training vehicles
        if self.support_max_age:
            self.curve = apply_support(self.curve, self.support_max_age)
            self.q10 = apply_support(self.q10, self.support_max_age)
            self.q90 = apply_support(self.q90, self.support_max_age)
        self.smoothing_window = int(self.cal.get("smoothing_window", 1))                      # 1 = none (artifacts older than the final review)
        if self.smoothing_window > 1:
            self.curve = {f: smooth_cumulative(c, self.a_sup, self.smoothing_window) for f, c in self.curve.items()}
            self.q10 = {f: smooth_cumulative(c, self.a_sup, self.smoothing_window) for f, c in self.q10.items()}
            self.q90 = {f: smooth_cumulative(c, self.a_sup, self.smoothing_window) for f, c in self.q90.items()}
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
        reliability, reason = "ok", None
        if fuel == "electric":
            reliability, reason = "low", "no training data exist for electric vehicles: the petrol curve is used"
        elif fuel_key in self.support_max_age and a > self.support_max_age[fuel_key] and fuel_key != "petrol":
            reliability, reason = "low", (f"the training data hold too few {fuel_key.replace('lpg_cng', 'LPG/CNG')} vehicles older than {self.support_max_age[fuel_key]} years "
                                          "(under 30 per year of age): from there on the yearly growth of petrol vehicles was used")
        annual = est / max(a, 1) if a > 0 else est
        if reliability == "ok" and a > 0 and annual > MAX_PLAUSIBLE_ANNUAL_KM:
            reliability, reason = "low", (f"the estimate implies about {int(round(annual, -3)):,} km per year, more than the official statistics publish for any group "
                                          "(highest average 28,400 km, leasing cars): the combination of age, fuel type and ownership is not covered by them")
        return MileageEstimate(km=int(round(est, -2)), km_low=int(round(lo, -2)), km_high=int(round(hi, -2)), annual_km=int(round(annual, -2)), notes=tuple(notes),
                               reliability=reliability, reliability_reason=reason)
