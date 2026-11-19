"""Model 2 inference: relative risk that the NEXT annual inspection finds a defect, by system.

Four XGBoost variants per system exist (cold, cold_odo, hist, hist_odo); the one used depends only on which REAL inputs are available:
  * history   = the result of the vehicle's previous annual INSPECTION (never a maintenance record: that equivalence was not validated);
  * odometer  = a MEASURED odometer at that inspection (the Model 1 estimate is deliberately not a feature: it did not improve any metric).

The model was trained on UK MOT data and validated on Dutch RDW data; it has NOT been validated on Israeli vehicles. The score is therefore reported only as a
RELATIVE position:
  * main indicator   - the position of the vehicle's score among ALL reference vehicles (UK, out-of-sample scores, every age): three levels Low / Moderate / High;
  * complementary    - the position among reference vehicles of the SAME AGE (lower / typical / higher), explicitly relative to that age group.
The score is always computed for a STANDARD interval of 12 months to the next inspection (the planned interval of a plate is not used: it never improved the
ranking out of sample and made identical vehicles look different).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

SYSTEMS = ["brakes", "electrical", "engine_emissions"]
HIST_COLUMNS = {"brakes": "cur_brakes", "electrical": "cur_electrical", "engine_emissions": "cur_engine_emissions"}
LEVELS = ("low", "moderate", "high")


@dataclass(frozen=True)
class RiskInputs:
    age_year: int                       # calendar year of the last inspection minus year of first use
    fuel: str                           # petrol | diesel | hybrid | electric | lpg_cng
    make: str                           # title case, UK vocabulary (e.g. "Toyota", "Mercedes-Benz", "Bmw")
    previous: dict | None = None        # {"brakes": bool, "electrical": bool, "engine_emissions": bool, "any_defect": bool} from the previous INSPECTION
    odometer_km: float | None = None    # measured odometer at that inspection


@dataclass
class SystemRisk:
    system: str
    probability: float                  # raw model output at a 12-month interval; internal only (UK-calibrated, not validated for Israel): never shown as a probability
    reference_percentile: float         # 0-100: share of reference vehicles (all ages) with a lower score
    level: str                          # low | moderate | high
    same_age_percentile: float          # 0-100 among reference vehicles of the same age
    same_age_label: str                 # lower | typical | higher
    observed_rates: dict[str, float]    # share of reference vehicles of each level that had a defect at the next inspection (UK data)


@dataclass
class RiskResult:
    covered: bool
    reasons: list[str] = field(default_factory=list)
    variant: str | None = None
    uses_history: bool = False
    uses_measured_odometer: bool = False
    systems: list[SystemRisk] = field(default_factory=list)


class RiskModel:
    def __init__(self, artifact_dir: Path):
        d = Path(artifact_dir) / "model2"
        self.card = json.loads((d / "model2_card.json").read_text(encoding="utf-8"))
        self.reference = json.loads((d / "model2_reference.json").read_text(encoding="utf-8"))
        self.variants: dict[str, list[str]] = self.card["variants"]
        self.cats: dict[str, list[str]] = self.card["categories"]
        self.makes = set(self.card["makes_in_training"])
        self.fuels = list(self.card["coverage"]["fuels"])
        self.age_min, self.age_max = self.card["coverage"]["age_years_at_last_inspection"]
        self.standard_gap = float(self.reference["standard_gap_years"])
        self.quantile_pct = np.array(self.reference["quantile_levels"]) * 100          # 0, 1, ..., 100
        self.ref_quantiles = {k: np.array(v) for k, v in self.reference["reference_quantiles"].items()}
        self.decile_pct = np.array(self.reference["decile_levels"]) * 100
        self.same_age = self.reference["same_age_score_deciles"]
        self.cuts = self.reference["level_cut_percentiles"]
        self.rates = {(r["variant"], r["system"]): {k: r[k]["rate"] for k in LEVELS} for r in self.reference["level_rates"] if r["data"] == "UK cross-fitted"}
        self.boosters: dict[str, xgb.Booster] = {}
        for v in self.variants:
            for s in SYSTEMS:
                b = xgb.Booster()
                b.load_model(str(d / f"{v}_{s}.json"))
                self.boosters[f"{v}/{s}"] = b

    # ---------------------------------------------------------------- coverage
    def check_coverage(self, x: RiskInputs) -> list[str]:
        reasons = []
        if x.fuel not in self.fuels:
            reasons.append(f"fuel type '{x.fuel}' is not covered (training data: {', '.join(self.fuels)})")
        if not (self.age_min <= x.age_year <= self.age_max):
            reasons.append(f"vehicle age {x.age_year} at the last inspection is outside the covered range {self.age_min}-{self.age_max} years")
        return reasons

    def choose_variant(self, x: RiskInputs) -> str:
        hist, odo = x.previous is not None, x.odometer_km is not None
        return {(False, False): "cold", (False, True): "cold_odo", (True, False): "hist", (True, True): "hist_odo"}[(hist, odo)]

    # ---------------------------------------------------------------- prediction
    def _frame(self, x: RiskInputs, variant: str) -> pd.DataFrame:
        row = {"age_year": x.age_year, "gap_next": self.standard_gap, "fuel": x.fuel, "make_c": x.make if x.make in self.makes else "OTHER",
               "km": x.odometer_km if x.odometer_km is not None else np.nan}
        if x.previous is not None:
            prev = x.previous
            row.update({"cur_brakes": int(bool(prev.get("brakes"))), "cur_electrical": int(bool(prev.get("electrical"))), "cur_engine_emissions": int(bool(prev.get("engine_emissions"))),
                        "cur_any_defect": int(bool(prev.get("any_defect")) or any(bool(prev.get(k)) for k in HIST_COLUMNS))})
        df = pd.DataFrame([row])[self.variants[variant]]
        for c in ("fuel", "make_c"):
            if c in df:
                df[c] = pd.Categorical(df[c], categories=self.cats[c])
        return df

    def reference_percentile(self, variant: str, system: str, p: float) -> float:
        """Share of the reference vehicles (all ages, out-of-sample UK scores, same variant) whose score is lower; piecewise-linear between 101 quantiles."""
        return float(np.interp(p, self.ref_quantiles[f"{variant}/{system}"], self.quantile_pct))

    def same_age_percentile(self, variant: str, system: str, age: int, p: float) -> float:
        dec = self.same_age[f"{variant}/{system}"][str(min(max(age, self.age_min), self.age_max))]
        return float(np.interp(p, dec, self.decile_pct, left=5.0, right=95.0))

    def level_of(self, system: str, percentile: float) -> str:
        a, b = self.cuts[system]
        return "low" if percentile <= a else ("moderate" if percentile <= b else "high")

    def predict(self, x: RiskInputs) -> RiskResult:
        reasons = self.check_coverage(x)
        if reasons:
            return RiskResult(covered=False, reasons=reasons)
        notes = []
        if x.make not in self.makes:
            notes.append(f"make '{x.make}' is outside the {len(self.makes)} makes seen in training: grouped with 'other makes' (less evidence)")
        variant = self.choose_variant(x)
        dm = xgb.DMatrix(self._frame(x, variant), enable_categorical=True)
        out = []
        for s in SYSTEMS:
            p = float(self.boosters[f"{variant}/{s}"].predict(dm)[0])
            pct = self.reference_percentile(variant, s, p)
            sa = self.same_age_percentile(variant, s, x.age_year, p)
            out.append(SystemRisk(system=s, probability=p, reference_percentile=pct, level=self.level_of(s, pct), same_age_percentile=sa,
                                  same_age_label="higher" if sa >= 80 else ("lower" if sa <= 20 else "typical"), observed_rates=self.rates[(variant, s)]))
        return RiskResult(covered=True, reasons=notes, variant=variant, uses_history=x.previous is not None, uses_measured_odometer=x.odometer_km is not None, systems=out)
