"""Shared pieces of the Model 1 experiments (data parts, preprocessing, metrics). Used by m1_ablation and model1_train."""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
import mileage_data as md  # noqa: E402
from official_data import odometers  # noqa: E402
from synthesis import SequentialCART, fidelity  # noqa: E402
from app.ml.spec_features import M1_FEATURES, FrequencyEncoder, VehicleKNNImputer, make_model_key, owner_type  # noqa: E402

SEED = 42
IMPUTE = ["age", "engine_cc", "automatic", "fuel"]
KEEP = M1_FEATURES + ["km"]


def kaggle():
    P = pd.concat([md.load_clean(k)[0] for k in ("d7_uk", "d8_in", "d3_cardekho")], ignore_index=True)
    P["engine_cc"] = P.engine_cc.where(P.engine_cc > 0)
    P.loc[P.fuel == "electric", "engine_cc"] = 0.0
    P["automatic"] = P.transmission.map({"automatic": 1.0, "manual": 0.0})
    P["owner_type"] = P.owner_count.map(owner_type)
    P["make_model"] = [make_model_key(a, b) for a, b in zip(P.make, P.model)]
    tr, te = train_test_split(P, test_size=0.2, random_state=SEED, stratify=P["source"])        # the SAME 80/20 split as the previous Model 1
    fit, val = train_test_split(tr, test_size=0.15, random_state=SEED, stratify=tr["source"])
    return fit.reset_index(drop=True), val.reset_index(drop=True), te.reset_index(drop=True)


def prep(encoding, scaler=None):
    enc = TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=SEED)) if encoding == "target" else FrequencyEncoder()
    sc = [("scale", scaler)] if scaler is not None else []
    sc2 = [("scale", type(scaler)())] if scaler is not None else []
    return ColumnTransformer([("numeric", Pipeline([("impute", VehicleKNNImputer(5))] + sc), IMPUTE),
                              ("low_card", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["fuel", "owner_type"]),
                              ("make_model", Pipeline([("encode", enc)] + sc2), ["make_model"])])


def xgb(**kw):
    base = dict(n_estimators=500, learning_rate=0.05, max_depth=6, min_child_weight=20, subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0, tree_method="hist", n_jobs=8, random_state=SEED,
                monotone_constraints="(1)")
    base.update(kw)
    return XGBRegressor(**base)


def metrics(y, p):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 0, None)
    return {"rmse": float(np.sqrt(np.mean((y - p) ** 2))), "mae": float(np.mean(np.abs(y - p))), "r2": float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2)), "bias": float(np.mean(p - y)), "n": int(len(y))}


def synth_kaggle(fit, n, seed=1):
    g = SequentialCART(["source", "age", "fuel", "make_model", "engine_cc", "automatic", "owner_type", "km"], ["source", "fuel", "make_model", "owner_type"], ["km"], min_leaf=20).fit(fit)
    s = g.sample(n, seed=seed); s["age"] = s.age.round(); return s


def synth_official(off_fit, n, seed=1):
    g = SequentialCART(["fuel", "age", "make_model", "engine_cc", "km"], ["fuel", "make_model"], ["km"], min_leaf=30).fit(off_fit)
    s = g.sample(n, seed=seed); s["automatic"] = np.nan; s["owner_type"] = "Unknown"; s["km"] = s.km.clip(0, 500_000); return s, g
