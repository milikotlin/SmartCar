"""Model 2 inference: risk that the NEXT annual inspection finds a defect, by system.

Four XGBoost variants per system exist (cold, cold_odo, hist, hist_odo); the one used depends only on which REAL inputs are available:
  * history   = the result of the vehicle's previous annual INSPECTION (never a maintenance record: that equivalence was not validated);
  * odometer  = a MEASURED odometer at that inspection (the Model 1 estimate is deliberately not a feature: it did not improve any metric).
The model was trained on UK MOT data and validated on Dutch RDW data. It has NOT been validated on Israeli vehicles, so the API reports a risk
RANK among vehicles of the same age (the thing the model does well) and keeps the foreign-calibrated probability as a clearly labelled secondary figure.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

SYSTEMS = ["brakes", "electrical", "engine_emissions"]
HIST_COLUMNS = {"brakes": "cur_brakes", "electrical": "cur_electrical", "engine_emissions": "cur_engine_emissions"}


@dataclass(frozen=True)
class RiskInputs:
    age_year: int                       # calendar year of the last inspection minus year of first use
    gap_next: float                     # planned interval to the next inspection (years)
    fuel: str                           # petrol | diesel | hybrid | electric | lpg_cng
    make: str                           # title case, UK vocabulary (e.g. "Toyota", "Mercedes-Benz", "Bmw")
    previous: dict | None = None        # {"brakes": bool, "electrical": bool, "engine_emissions": bool, "any_defect": bool} from the previous INSPECTION
    odometer_km: float | None = None    # measured odometer at that inspection


@dataclass
class SystemRisk:
    system: str
    probability: float                  # foreign-calibrated (UK) probability that the next inspection finds a defect in this system
    relative_risk: float                # probability / average UK rate at the same age
    percentile_same_age: int            # rank among vehicles of the same age (cross-fitted UK scores)
    band: str                           # lower | typical | higher


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
        self.variants: dict[str, list[str]] = self.card["variants"]
        self.cats: dict[str, list[str]] = self.card["categories"]
        self.makes = set(self.card["makes_in_training"])
        self.fuels = list(self.card["coverage"]["fuels"])
        self.age_min, self.age_max = self.card["coverage"]["age_years_at_last_inspection"]
        self.levels = np.array(self.card["decile_levels"])
        self.deciles = self.card["same_age_score_deciles"]
        self.ref_rate = self.card["reference_rate_by_age"]
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
        row = {"age_year": x.age_year, "gap_next": x.gap_next, "fuel": x.fuel, "make_c": x.make if x.make in self.makes else "OTHER", "km": x.odometer_km if x.odometer_km is not None else np.nan}
        if x.previous is not None:
            prev = x.previous
            row.update({"cur_brakes": int(bool(prev.get("brakes"))), "cur_electrical": int(bool(prev.get("electrical"))), "cur_engine_emissions": int(bool(prev.get("engine_emissions"))),
                        "cur_any_defect": int(bool(prev.get("any_defect")) or any(bool(prev.get(k)) for k in HIST_COLUMNS))})
        df = pd.DataFrame([row])[self.variants[variant]]
        for c in ("fuel", "make_c"):
            if c in df:
                df[c] = pd.Categorical(df[c], categories=self.cats[c])
        return df

    def _percentile(self, variant: str, system: str, age: int, p: float) -> int:
        dec = self.deciles[f"{variant}/{system}"]
        key = str(min(max(age, self.age_min), self.age_max))
        q = np.array(dec[key])
        # piecewise-linear rank between the deciles; below the 10th / above the 90th percentile the rank is clamped to 5 / 95
        pct = float(np.interp(p, q, self.levels, left=0.05, right=0.95)) * 100
        return int(round(min(max(pct, 1), 99)))

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
            age_key = str(min(max(x.age_year, self.age_min), self.age_max))
            pct = self._percentile(variant, s, x.age_year, p)
            q = self.deciles[f"{variant}/{s}"][age_key]
            band = "higher" if p >= q[7] else ("lower" if p <= q[1] else "typical")      # 80th / 20th percentile of the same age
            out.append(SystemRisk(system=s, probability=p, relative_risk=p / max(self.ref_rate[s][age_key], 1e-6), percentile_same_age=pct, band=band))
        return RiskResult(covered=True, reasons=notes, variant=variant, uses_history=x.previous is not None, uses_measured_odometer=x.odometer_km is not None, systems=out)
