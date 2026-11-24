"""Feature definitions shared by the offline training (ml/src/model1_train.py, model2_train.py) and the API, for the models built exactly as
Smart_Car_Models.pdf specifies. Anything a pickled pipeline refers to must live here, so that the backend can load it.
"""
import re

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import KNNImputer

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


FUEL_LEVELS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]


class VehicleKNNImputer(BaseEstimator, TransformerMixin):
    """KNN imputer (K=5) for engine size and transmission "based on similar vehicles": similar = same fuel, close age and engine, on STANDARDISED columns.

    Input columns: age, engine_cc, automatic, fuel. Output: age, engine_cc, automatic. The neighbours are real Kaggle listings with both values present (the only
    source that has the transmission), at most `max_reference` of them; identical queries are imputed once. An electric car has no engine: 0, never imputed.
    """

    def __init__(self, n_neighbors: int = 5, max_reference: int = 8000, random_state: int = 42):
        self.n_neighbors, self.max_reference, self.random_state = n_neighbors, max_reference, random_state

    @staticmethod
    def _matrix(X) -> np.ndarray:
        d = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=["age", "engine_cc", "automatic", "fuel"])
        num = d[["age", "engine_cc", "automatic"]].apply(pd.to_numeric, errors="coerce").to_numpy(float).copy()
        num[(d["fuel"] == "electric").to_numpy(), 1] = 0.0
        return np.column_stack([num] + [(d["fuel"] == f).to_numpy(float) for f in FUEL_LEVELS])

    def _scale(self, m: np.ndarray) -> np.ndarray:
        out = m.copy()
        out[:, :3] = (m[:, :3] - self.mean_) / self.std_
        out[:, 3:] = m[:, 3:] * 3.0                       # another fuel is further away than any usual difference in age or engine
        return out

    def fit(self, X, y=None):
        m = self._matrix(X)
        ref = m[~np.isnan(m[:, :3]).any(axis=1)]
        rng = np.random.default_rng(self.random_state)
        if len(ref) > self.max_reference:
            ref = ref[rng.choice(len(ref), self.max_reference, replace=False)]
        self.mean_, self.std_ = ref[:, :3].mean(axis=0), ref[:, :3].std(axis=0) + 1e-9
        self.imputer_ = KNNImputer(n_neighbors=self.n_neighbors).fit(self._scale(ref))
        return self

    def transform(self, X) -> np.ndarray:
        m = self._matrix(X)
        miss = np.isnan(m[:, :3]).any(axis=1)
        if miss.any():
            q = np.where(np.isnan(m[miss]), -999.0, m[miss])
            uniq, inv = np.unique(q, axis=0, return_inverse=True)
            uniq = np.where(uniq == -999.0, np.nan, uniq)
            filled = self.imputer_.transform(self._scale(uniq))
            filled[:, :3] = filled[:, :3] * self.std_ + self.mean_
            m[miss] = filled[np.asarray(inv).ravel()]
        return m[:, :3]

    def get_feature_names_out(self, input_features=None):
        return np.array(["age", "engine_cc", "automatic"])


# ------------------------------------------------------------------ Model 2 (predictive maintenance classifier)
# Maintenance_Type of Dataset 1 is NOT used: in the 250K file it determines the label exactly (every "Oil Check" is 0, every "Oil Change" is 1): data leakage.
M2_FEATURES = ["vehicle_age", "km", "km_measured", "days_since_last_maintenance", "failure_history", "brand_reliability_index",
               "d4_engine_fault_rate", "d4_brake_fault_rate", "d4_battery_fault_rate"]
M2_EV_EXTRA = ["last_service_distance", "service_frequency", "time_since_last_fault", "driving_distance"]          # Dataset 5 columns left after the strict dropping
M2_EV_FEATURES = M2_FEATURES + M2_EV_EXTRA
KM_BINS = [0, 20_000, 50_000, 100_000, 150_000, 200_000, 300_000, np.inf]       # mileage groups for the Dataset 4 aggregation
