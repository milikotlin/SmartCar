"""Model 2 (Smart_Car_Models.pdf): predictive maintenance classifier with a combustion branch (Kaggle Dataset 1 + Dataset 4 failure distribution) and an electric / hybrid branch
(Dataset 5 + the electric rows of Dataset 1), both augmented with synthetic vehicles generated from real inspections. Trained by ml/src/model2_train.py; this module only predicts.

The score is calibrated on real UK inspection outcomes and shown as three levels (thirds of real vehicles), never as a percentage: there are no Israeli outcomes to check it against.
An input that is not known stays unknown (the model was trained with masked inputs); it is never replaced by zero.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.spec_features import KM_BINS, M2_EV_FEATURES, M2_FEATURES

LEVELS = ("low", "moderate", "high")
SCENARIO_NAMES = {(False, False): "no records (plate only)", (True, False): "odometer known", (False, True): "last inspection known", (True, True): "odometer + last inspection"}


@dataclass
class SpecRiskInputs:
    vehicle_age: int
    km: float | None                                # the odometer shown to the user (reported, recorded or the Model 1 estimate)
    km_source: str                                  # user_reported | measured | estimated (Model 1)
    fuel: str
    make: str
    km_model_scale: float | None = None             # the same odometer on Model 1's own (training) scale; None: `km` is used as it is
    days_since_last_maintenance: float | None = None
    failure_history: int | None = None              # None = no inspection on file; 0 = the last one was clean; n = the last one had a defect (n inspections with a defect on file)
    last_service_distance: float | None = None      # km since the latest service (electric / hybrid branch)


@dataclass
class SpecRiskResult:
    branch: str                                     # "ice" | "ev"
    probability: float                              # calibrated on real UK vehicles; shown only as a level
    level: str
    cut_probabilities: list[float]
    observed_rate_by_level: list[float | None]
    inputs: dict = field(default_factory=dict)
    assumed: list[str] = field(default_factory=list)  # inputs that are not known for this vehicle
    scenario: str = ""                              # what was known (key of card[branch]["by_scenario"])
    in_data_range: bool = True                      # vehicle age inside the real data (3-20 years)


class SpecRiskModel:
    def __init__(self, artifact_dir: Path):
        d = Path(artifact_dir) / "spec"
        self.pipelines = {b: joblib.load(d / f"model2_{b}_pipeline.joblib") for b in ("ice", "ev")}
        self.card = json.loads((d / "model2_card.json").read_text(encoding="utf-8"))
        self.bri = self.card["brand_reliability_index"]
        self.d4 = self.card["dataset4_aggregation"]
        self.age_range = tuple(self.card["data_age_range"])

    def brand_index(self, make: str) -> float:
        return float(self.bri["index"].get((make or "").strip().lower(), self.bri["default"]))

    def d4_rates(self, km: float | None) -> dict:
        b = 0 if km is None else int(np.clip(np.searchsorted(KM_BINS, float(km), side="right") - 1, 0, len(KM_BINS) - 2))
        r = self.d4["by_bin"][str(b)]
        return {"d4_engine_fault_rate": r["engine_failure_imminent"], "d4_brake_fault_rate": r["brake_issue_imminent"], "d4_battery_fault_rate": r["battery_issue_imminent"]}

    def predict(self, x: SpecRiskInputs) -> SpecRiskResult:
        branch = "ev" if x.fuel in ("electric", "hybrid") else "ice"
        part, cols = self.card[branch], M2_EV_FEATURES if branch == "ev" else M2_FEATURES
        km = x.km if x.km_model_scale is None else x.km_model_scale
        known_odo = x.km_source in ("user_reported", "measured")
        row = {"vehicle_age": x.vehicle_age, "km": km, "km_measured": float(known_odo), "days_since_last_maintenance": x.days_since_last_maintenance,
               "failure_history": None if x.failure_history is None else min(x.failure_history, 2), "brand_reliability_index": self.brand_index(x.make), **self.d4_rates(km),
               "last_service_distance": x.last_service_distance}
        assumed = []
        if x.days_since_last_maintenance is None:
            assumed.append("days since the last maintenance")
        if x.failure_history is None:
            assumed.append("result of the last inspection")
        if not known_odo:
            assumed.append("true odometer (Model 1 estimate used)")
        if branch == "ev" and x.last_service_distance is None:
            assumed.append("km since the last service")
        df = pd.DataFrame([{c: row.get(c) for c in cols}], columns=cols).astype(float)
        situation = SCENARIO_NAMES[(known_odo, x.failure_history is not None)]
        a, b = part["platt_by_scenario"][situation]                      # calibrated on real UK validation vehicles for which the same things were known
        raw = float(np.clip(self.pipelines[branch].predict_proba(df)[0, 1], 1e-6, 1 - 1e-6))
        p = float(1 / (1 + np.exp(-(a * np.log(raw / (1 - raw)) + b))))
        cuts = part["levels"]["cut_probabilities"]
        level = LEVELS[0] if p <= cuts[0] else (LEVELS[1] if p <= cuts[1] else LEVELS[2])
        # what the dashboard shows: the odometer as the user knows it, next to the value on the model's scale
        shown = {"vehicle_age": x.vehicle_age, "km": x.km, "km_source": x.km_source, "km_model_scale": km, **{c: row.get(c) for c in cols if c not in ("vehicle_age", "km", "km_measured")}}
        return SpecRiskResult(branch=branch, probability=p, level=level, cut_probabilities=cuts, observed_rate_by_level=part["levels"]["test_rate_by_level"],
                              inputs={k: v for k, v in shown.items() if v is not None}, assumed=assumed, scenario=situation,
                              in_data_range=self.age_range[0] <= x.vehicle_age <= self.age_range[1])
