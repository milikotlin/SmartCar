"""Feature definitions shared by the offline training (ml/src/spec_model1.py, spec_model2.py) and the API, for the models built exactly as
Smart_Car_Models.pdf specifies. Anything a pickled pipeline refers to must live here, so that the backend can load it.
"""
import re

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

# ------------------------------------------------------------------ Model 1 (odometer regression)
M1_NUMERIC = ["age", "engine_cc", "automatic"]          # automatic: 1 automatic / 0 manual / NaN unknown (filled by the KNN imputer, K=5)
M1_LOW_CARD = ["fuel", "owner_type"]                    # One-Hot Encoding (transmission is binary, so its one-hot is the single 0/1 column above)
M1_HIGH_CARD = ["make_model"]                           # Target Encoding or Frequency Encoding, chosen by cross-validation
M1_FEATURES = M1_NUMERIC + M1_LOW_CARD + M1_HIGH_CARD
OWNER_TYPES = {1: "First", 2: "Second", 3: "Third", 4: "Fourth & Above"}


def owner_type(count) -> str:
    """Dataset 8 `Owner_Type` = how many owners the car has had (First, Second, ...); unknown elsewhere."""
    if count is None or (isinstance(count, float) and np.isnan(count)):
        return "Unknown"
    return OWNER_TYPES[min(max(int(count), 1), 4)]


def make_model_key(make, model) -> str:
    """'Toyota' + 'AURIS HYBRID' -> 'toyota|auris' (first word of the model name, the part the three datasets and the registry share)."""
    mk = str(make or "").strip().lower()
    words = re.findall(r"[a-z0-9]+", str(model or "").lower())
    return f"{mk}|{words[0] if words else ''}"


class FrequencyEncoder(BaseEstimator, TransformerMixin):
    """Replaces a category by its share of the training rows (unseen categories -> 0)."""

    def fit(self, X, y=None):
        col = pd.Series(np.asarray(X).ravel())
        self.freq_ = col.value_counts(normalize=True).to_dict()
        return self

    def transform(self, X):
        col = pd.Series(np.asarray(X).ravel())
        return col.map(self.freq_).fillna(0.0).to_numpy().reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.array(["make_model_frequency"])


# ------------------------------------------------------------------ Model 2 (predictive maintenance classifier)
M2_NUMERIC = ["vehicle_age", "km", "days_since_last_maintenance", "failure_history", "brand_reliability_index",
              "d4_engine_fault_rate", "d4_brake_fault_rate", "d4_battery_fault_rate"]
M2_CATEGORICAL = ["maintenance_type"]
M2_FEATURES = M2_NUMERIC + M2_CATEGORICAL
M2_EV_NUMERIC = ["last_service_distance", "service_frequency", "time_since_last_fault", "driving_distance"]
MAINTENANCE_TYPES = ["Oil", "Tires", "Brakes", "Battery/Electrical", "Major repair", "Routine inspection"]
# Dataset 1 vocabulary (two generators with different labels) -> one shared vocabulary
D1_MAINTENANCE_TYPE = {"Oil Change": "Oil", "Oil Check": "Oil", "Tire Rotation": "Tires", "Tire Replacement": "Tires", "Brake Service": "Brakes",
                       "Battery Service": "Battery/Electrical", "Electrical Repair": "Battery/Electrical", "Engine Overhaul": "Major repair",
                       "Transmission Service": "Major repair", "Cooling System Repair": "Major repair", "Routine Inspection": "Routine inspection"}
# our maintenance_records.maintenance_category -> the same vocabulary
CATEGORY_TO_MAINTENANCE_TYPE = {"oil": "Oil", "tires": "Tires", "brakes": "Brakes", "brake_fluid": "Brakes", "battery": "Battery/Electrical",
                                "coolant": "Routine inspection", "filters": "Routine inspection", "other": "Routine inspection"}
KM_BINS = [0, 20_000, 50_000, 100_000, 150_000, 200_000, 300_000, np.inf]       # mileage groups for the Dataset 4 aggregation
