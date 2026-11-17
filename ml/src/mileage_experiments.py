"""Building blocks for the Model 1 experiments (notebook 01).

Everything here is for EXPERIMENTATION: nothing is exported or wired into the backend.
Encoders that use the target (TargetEncoder) live INSIDE the sklearn Pipeline so they are fit
on the training fold only (no target leakage into validation/test rows).
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from xgboost import XGBRegressor

SEED = 42
N_JOBS = 8


class FrequencyEncoder(BaseEstimator, TransformerMixin):
    """Category -> its relative frequency in the training fold (unseen -> 0)."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.maps_ = [X[c].astype(str).value_counts(normalize=True).to_dict() for c in X.columns]
        return self

    def transform(self, X):
        X = pd.DataFrame(X)
        cols = [X[c].astype(str).map(m).fillna(0.0).to_numpy() for c, m in zip(X.columns, self.maps_)]
        return np.column_stack(cols)

    def get_feature_names_out(self, names=None):
        return np.array([f"freq_{i}" for i in range(len(self.maps_))])


def add_make_model(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["make_model"] = df["make"].astype(str) + "|" + df["model"].astype(str)
    return df


def _cat_encoder(kind: str):
    if kind == "ohe":
        return OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=100, sparse_output=False)
    if kind == "target":
        return TargetEncoder(target_type="continuous", smooth="auto", cv=5, shuffle=True, random_state=SEED)
    if kind == "freq":
        return FrequencyEncoder()
    raise ValueError(kind)


def make_estimator(algo: str):
    if algo == "ridge":
        return Ridge(alpha=1.0)
    if algo == "rf":
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=5, max_features=0.5, n_jobs=N_JOBS, random_state=SEED)
    if algo == "xgb":
        return XGBRegressor(
            n_estimators=500, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=5, tree_method="hist", n_jobs=N_JOBS, random_state=SEED,
        )
    if algo == "xgb_log":
        return TransformedTargetRegressor(regressor=make_estimator("xgb"), func=np.log1p, inverse_func=np.expm1)
    raise ValueError(algo)


def build_pipeline(numeric=("age",), low_card=("fuel", "transmission"), make_enc="ohe", model_enc=None, algo="xgb"):
    """numeric: numeric columns; low_card: categorical columns (OHE); make_enc / model_enc: ohe|target|freq|None."""
    numeric, low_card = list(numeric), list(low_card)
    transformers = []
    if numeric:
        steps = [("imp", SimpleImputer(strategy="median"))]
        if algo == "ridge":
            steps.append(("scale", StandardScaler()))
        transformers.append(("num", Pipeline(steps), numeric))
    if low_card:
        transformers.append((
            "low",
            Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="unknown")), ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]),
            low_card,
        ))
    if make_enc:
        transformers.append(("make", _cat_encoder(make_enc), ["make"]))
    if model_enc:
        transformers.append(("model", _cat_encoder(model_enc), ["make_model"]))
    return Pipeline([("prep", ColumnTransformer(transformers)), ("est", make_estimator(algo))])


def regression_metrics(y_true, y_pred, weights=None) -> dict:
    y_pred = np.clip(y_pred, 0, None)
    w = None if weights is None else np.asarray(weights, dtype=float)
    mse = np.average((np.asarray(y_true) - y_pred) ** 2, weights=w)
    mae = np.average(np.abs(np.asarray(y_true) - y_pred), weights=w)
    return {"RMSE": float(np.sqrt(mse)), "MAE": float(mae), "R2": float(r2_score(y_true, y_pred, sample_weight=w))}


def raking_weights(df: pd.DataFrame, targets: dict, n_iter: int = 25) -> np.ndarray:
    """Importance weights so the weighted marginals of `df` match the target (Israeli) marginals.

    targets = {column: {category: probability}} ; rows whose category is absent from a target get weight 0.
    """
    w = np.ones(len(df))
    for c, tgt in targets.items():
        w = w * df[c].isin(tgt.keys()).to_numpy()
    for _ in range(n_iter):
        for c, tgt in targets.items():
            cur = pd.Series(w).groupby(df[c].to_numpy()).sum()
            cur = cur / cur.sum()
            factor = df[c].map(lambda k: (tgt.get(k, 0) / cur[k]) if k in cur.index and cur[k] > 0 else 0).to_numpy()
            w = w * factor
    return w / w.sum() * len(df)


def paired_bootstrap_delta(y, pred_a, pred_b, n=400, seed=0, weights=None) -> dict:
    """Bootstrap CI for RMSE(a) - RMSE(b) on the SAME rows (negative => a is better)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    pa, pb = np.clip(pred_a, 0, None), np.clip(pred_b, 0, None)
    w = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    deltas = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        ra = np.sqrt(np.average((y[idx] - pa[idx]) ** 2, weights=w[idx]))
        rb = np.sqrt(np.average((y[idx] - pb[idx]) ** 2, weights=w[idx]))
        deltas.append(ra - rb)
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return {"delta_rmse_mean": float(np.mean(deltas)), "ci95_low": float(lo), "ci95_high": float(hi)}
