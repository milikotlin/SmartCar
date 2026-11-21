"""Model 2 built as Smart_Car_Models.pdf specifies: predictive maintenance classifier (Dataset 1 for combustion vehicles, enriched with the Dataset 4
failure distribution by mileage; a dedicated Dataset 5 model for electric / hybrid vehicles). Trained offline by ml/src/spec_model2.py.

The output is a probability score; the dashboard shows it as three levels (Low / Moderate / High = tertiles of the training probabilities), never as a
percentage, because the labels of Datasets 1 and 5 are synthetic and the model has not been validated on real vehicles (see docs/MODEL_CARDS.md).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.spec_features import KM_BINS, M2_EV_NUMERIC, M2_FEATURES

LEVELS = ("low", "moderate", "high")


@dataclass
class SpecRiskInputs:
    vehicle_age: int
    km: float | None
    km_source: str                                  # user_reported | measured | estimated (Model 1)
    fuel: str
    make: str
    days_since_last_maintenance: float | None = None
    failure_history: int = 0                        # recorded inspection results with a defect
    maintenance_type: str | None = None             # of the latest maintenance record, in the Dataset 1 vocabulary
    last_service_distance: float | None = None      # km since the latest service (EV model)


@dataclass
class SpecRiskResult:
    branch: str                                     # "ice" (Dataset 1) | "ev" (Dataset 5)
    probability: float                              # internal; shown only as a level
    level: str
    cut_probabilities: list[float]
    observed_rate_by_level: list[float | None]
    inputs: dict = field(default_factory=dict)
    assumed: list[str] = field(default_factory=list)  # inputs that were unknown and replaced by the training median


class SpecRiskModel:
    def __init__(self, artifact_dir: Path):
        d = Path(artifact_dir) / "spec"
        self.ice = joblib.load(d / "model2_ice_pipeline.joblib")
        self.ev = joblib.load(d / "model2_ev_pipeline.joblib")
        self.card = json.loads((d / "model2_card.json").read_text(encoding="utf-8"))
        self.bri = self.card["brand_reliability_index"]
        self.d4 = self.card["dataset4_aggregation"]

    def brand_index(self, make: str) -> float:
        return float(self.bri["index"].get((make or "").strip().lower(), self.bri["default"]))

    def d4_rates(self, km: float | None) -> dict:
        b = 0 if km is None else int(np.clip(np.searchsorted(KM_BINS, float(km), side="right") - 1, 0, len(KM_BINS) - 2))
        r = self.d4["by_bin"][str(b)]
        return {"d4_engine_fault_rate": r["engine_failure_imminent"], "d4_brake_fault_rate": r["brake_issue_imminent"], "d4_battery_fault_rate": r["battery_issue_imminent"]}

    def predict(self, x: SpecRiskInputs) -> SpecRiskResult:
        assumed = []
        if x.fuel in ("electric", "hybrid"):
            branch, part = "ev", self.card["ev"]
            row = {"last_service_distance": x.last_service_distance, "service_frequency": None, "time_since_last_fault": None, "driving_distance": None}
            for k, v in row.items():
                if v is None:
                    assumed.append(k.replace("_", " "))
            df = pd.DataFrame([row], columns=M2_EV_NUMERIC).astype(float)
            p = float(self.ev.predict_proba(df)[0, 1])
            inputs = {k: v for k, v in row.items() if v is not None}
        else:
            branch, part = "ice", self.card["ice"]
            row = {"vehicle_age": x.vehicle_age, "km": x.km, "days_since_last_maintenance": x.days_since_last_maintenance, "failure_history": x.failure_history,
                   "brand_reliability_index": self.brand_index(x.make), **self.d4_rates(x.km), "maintenance_type": x.maintenance_type or "Unknown"}
            if x.days_since_last_maintenance is None:
                assumed.append("days since the last maintenance")
            if x.maintenance_type is None:
                assumed.append("type of the last maintenance")
            df = pd.DataFrame([row], columns=M2_FEATURES)
            for c in M2_FEATURES:
                if c != "maintenance_type":
                    df[c] = df[c].astype(float)
            p = float(self.ice.predict_proba(df)[0, 1])
            inputs = {k: v for k, v in row.items() if v is not None}
            inputs["km_source"] = x.km_source
        cuts = part["levels"]["cut_probabilities"]
        level = LEVELS[0] if p <= cuts[0] else (LEVELS[1] if p <= cuts[1] else LEVELS[2])
        return SpecRiskResult(branch=branch, probability=p, level=level, cut_probabilities=cuts, observed_rate_by_level=part["levels"]["test_rate_by_level"],
                              inputs=inputs, assumed=assumed)
