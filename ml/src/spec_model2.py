"""Model 2 (predictive maintenance classifier) EXACTLY as Smart_Car_Models.pdf specifies, with the data pulled from Kaggle (kagglehub).

Specification -> implementation
  * Dataset 1 (Logistics Maintenance) = primary dataset for combustion vehicles          -> files "with_maintenance_required" (92K) + "predictive_maintenanceV2" (250K)
  * Dataset 5 (NEVs) = dedicated model for electric / hybrid vehicles (branching)          -> separate pipeline; the API uses it only for electric / hybrid vehicles
  * Dataset 4 (Telemetry) not used raw: group-by distribution of failure types -> features -> failure rates (engine / brakes / battery) per mileage group, joined to Dataset 1
  * Strict feature dropping: every telemetry sensor column removed from Datasets 1, 4, 5   -> only Vehicle_Age, mileage, maintenance history, brand, Dataset 4 rates remain
  * Vehicle_Age and Days_Since_Last_Maintenance as continuous features; Brand_Reliability_Index -> see brand_reliability_index() (real UK inspection outcomes)
  * Mileage predicted by Model 1                                                           -> Model 1 (spec) estimate for every Dataset 1 row
  * Class imbalance experiment: SMOTE vs class weights / scale_pos_weight                  -> two XGBoost pipelines, compared
  * XGBoost vs Logistic Regression baseline; hyper-parameter tuning that maximises Recall   -> RandomizedSearchCV, scoring = Recall (with a guard, see below)

Decisions forced by the data (documented in docs/MODEL_CARDS.md):
  * The third Dataset 1 file ("revised_logistics_dataset_V2", 250K) contains the 92K rows of the first file plus 158K noise-perturbed copies of them; using
    it would put near-duplicates of test rows into training. It is not used.
  * Leakage dropped: Anomalies_Detected (sensor anomalies; zero whenever the target is zero), Predictive_Score (a model output), Maintenance_Cost (the cost of
    the maintenance the target describes), and every sensor reading.
  * Dataset 4 has no vehicle age column: its failure distribution is grouped by mileage only.
  * Pure Recall is maximised by flagging every vehicle. The tuning maximises Recall among models whose precision is above the base rate (otherwise score 0).

Run:  ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/spec_model2.py
Writes backend/app/ml/artifacts/spec/model2_ice_pipeline.joblib, model2_ev_pipeline.joblib, model2_card.json and ml/spec_model2_results.json.
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, make_scorer, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
from kaggle_sources import SOURCE, find  # noqa: E402
from app.ml.spec_features import (D1_MAINTENANCE_TYPE, KM_BINS, M2_CATEGORICAL, M2_EV_NUMERIC, M2_FEATURES, M2_NUMERIC, MAINTENANCE_TYPES,  # noqa: E402
                                  make_model_key)

OUT = ROOT / "backend" / "app" / "ml" / "artifacts" / "spec"
SEED = 42
t0 = time.time()
D1_MAKE = {"Ford": "ford", "Chevy": "chevrolet", "Tesla": "tesla", "Volvo": "volvo", "MAN": "man", "Isuzu": "isuzu", "Scania": "scania", "Mercedes": "mercedes-benz"}


def log(msg):
    print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)


# ------------------------------------------------------------------ Brand_Reliability_Index from REAL inspection outcomes
def brand_reliability_index() -> dict:
    """50 = as reliable as the average vehicle OF THE SAME AGE; above 50 fewer defects than expected, below 50 more.
    index = 50 x expected / observed share of UK MOT vehicles with a defect at the next inspection (expected = age-adjusted), makes with >= 500 vehicles."""
    import model2_data as md2

    uk, _ = md2.uk_pairs()
    y = uk["next_any_defect"].astype(float)
    expected = uk["age_year"].map(y.groupby(uk["age_year"]).mean())
    g = pd.DataFrame({"make": uk["make"].str.lower(), "obs": y, "exp": expected}).groupby("make").agg(n=("obs", "size"), obs=("obs", "mean"), exp=("exp", "mean"))
    g = g[g.n >= 500]
    idx = (50 * g.exp / g.obs).clip(0, 100).round(1)
    return {"method": "50 x (age-adjusted expected / observed) share of vehicles with a defect at the next UK MOT inspection (2022 -> 2023, 660,202 pairs); 50 = average for the age",
            "default": 50.0, "index": {k: float(v) for k, v in idx.items()}, "vehicles": {k: int(v) for k, v in g.n.items()}}


# ------------------------------------------------------------------ Dataset 4: failure distribution by mileage group
def d4_rates() -> dict:
    d4 = pd.read_csv(find("d4_telemetry", "synthetic_telemetry_data.csv"))
    d4 = d4[["odometer_reading", "engine_failure_imminent", "brake_issue_imminent", "battery_issue_imminent"]]       # every other column is a sensor (dropped)
    d4["bin"] = pd.cut(d4.odometer_reading * 1.0, KM_BINS, right=False, labels=False)
    overall = {c: float(d4[c].mean()) for c in ("engine_failure_imminent", "brake_issue_imminent", "battery_issue_imminent")}
    table = {}
    for b in range(len(KM_BINS) - 1):
        sel = d4[d4.bin == b]
        k = 50                                                                                            # shrink small groups towards the overall rate
        table[str(b)] = {c: float((sel[c].sum() + k * overall[c]) / (len(sel) + k)) for c in overall}
        table[str(b)]["rows"] = int(len(sel))
    return {"bins_km": [float(x) for x in KM_BINS[:-1]], "overall": overall, "by_bin": table,
            "note": "Dataset 4 has no vehicle-age column, so the distribution is grouped by mileage only; groups are shrunk towards the overall rate (50 pseudo-rows)"}


def d4_features(km: pd.Series, d4: dict) -> pd.DataFrame:
    b = pd.cut(km.astype(float), KM_BINS, right=False, labels=False).fillna(0).astype(int).astype(str)
    return pd.DataFrame({"d4_engine_fault_rate": b.map(lambda x: d4["by_bin"][x]["engine_failure_imminent"]),
                         "d4_brake_fault_rate": b.map(lambda x: d4["by_bin"][x]["brake_issue_imminent"]),
                         "d4_battery_fault_rate": b.map(lambda x: d4["by_bin"][x]["battery_issue_imminent"])}, index=km.index)


# ------------------------------------------------------------------ Dataset 1
def load_d1(m1, bri: dict, d4: dict) -> pd.DataFrame:
    a = pd.read_csv(find("d1_logistics", "logistics_dataset_with_maintenance_required.csv"))
    b = pd.read_csv(find("d1_logistics", "logistics_predictive_maintenanceV2.csv"))
    ref_a = pd.to_datetime(a.Last_Maintenance_Date).max() + pd.Timedelta(days=1)
    rows = []
    for name, df, ref_year in (("d1_92k", a, ref_a.year), ("d1_v2_250k", b, pd.to_datetime(b.Last_Maintenance_Date).max().year)):
        days = (ref_a - pd.to_datetime(df.Last_Maintenance_Date)).dt.days if "Days_Since_Last_Maintenance" not in df else df.Days_Since_Last_Maintenance
        make = df.Make_and_Model.str.split().str[0].map(D1_MAKE)
        rows.append(pd.DataFrame({"file": name, "make": make, "vehicle_age": (ref_year - df.Year_of_Manufacture).clip(lower=0),
                                  "days_since_last_maintenance": days.astype(float), "failure_history": df.Failure_History.astype(float),
                                  "maintenance_type": df.Maintenance_Type.map(D1_MAINTENANCE_TYPE), "fuel": np.where(make == "tesla", "electric", "diesel"),
                                  "y": df.Maintenance_Required.astype(int)}))
    D = pd.concat(rows, ignore_index=True)
    # mileage predicted by Model 1 (spec): it depends only on age, fuel and make here, so it is computed once per combination
    combos = D[["vehicle_age", "fuel", "make"]].drop_duplicates()
    km = {}
    for r in combos.itertuples():
        f = {"age": int(r.vehicle_age), "engine_cc": None, "automatic": None, "fuel": r.fuel, "owner_type": "Unknown", "make_model": make_model_key(r.make, "")}
        km[(r.vehicle_age, r.fuel, r.make)] = m1.estimate(f, None).km
    D["km"] = [km[k] for k in zip(D.vehicle_age, D.fuel, D.make)]
    D["brand_reliability_index"] = D.make.map(bri["index"]).fillna(bri["default"])
    D = pd.concat([D, d4_features(D.km, d4)], axis=1)
    return D


def prep(scale: bool) -> ColumnTransformer:
    num = [("impute", SimpleImputer(strategy="median"))] + ([("scale", StandardScaler())] if scale else [])
    return ColumnTransformer([("numeric", Pipeline(num), M2_NUMERIC),
                              ("maintenance_type", OneHotEncoder(categories=[MAINTENANCE_TYPES], handle_unknown="ignore", sparse_output=False), M2_CATEGORICAL)])


def guarded_recall(base_rate: float):
    def score(y, p):
        prec = precision_score(y, p, zero_division=0)
        return recall_score(y, p) if prec > base_rate * 1.05 else 0.0
    return make_scorer(score)


SEARCH = {"model__max_depth": [3, 4, 6, 8], "model__learning_rate": [0.03, 0.05, 0.1], "model__n_estimators": [200, 400], "model__min_child_weight": [1, 5, 10], "model__subsample": [0.8, 1.0]}


def metrics(y, p, thr=0.5) -> dict:
    yhat = (p >= thr).astype(int)
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "recall": float(recall_score(y, yhat)),
            "precision": float(precision_score(y, yhat, zero_division=0)), "f1": float(f1_score(y, yhat)), "flagged_share": float(yhat.mean()), "base_rate": float(np.mean(y))}


def experiment(X, y, features_prep, search_rows: int | None, label: str, monotone: tuple | None = None) -> tuple[Pipeline, dict]:
    """SMOTE vs scale_pos_weight (XGBoost, tuned for guarded Recall) against Logistic Regression baselines; returns the chosen pipeline (refit, no sampler)."""
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    base = float(ytr.mean())
    spw = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    Xs, ys = (Xtr, ytr) if not search_rows or len(Xtr) <= search_rows else train_test_split(Xtr, ytr, train_size=search_rows, random_state=SEED, stratify=ytr)[0::2]
    cv = StratifiedKFold(3 if len(Xs) > 5000 else 5, shuffle=True, random_state=SEED)
    mono = {"monotone_constraints": monotone} if monotone else {}
    xgb = lambda **kw: XGBClassifier(tree_method="hist", n_jobs=8, random_state=SEED, eval_metric="logloss", **mono, **kw)
    candidates = {"XGBoost + SMOTE": ImbPipeline([("prep", features_prep(False)), ("smote", SMOTE(random_state=SEED)), ("model", xgb())]),
                  "XGBoost + scale_pos_weight": Pipeline([("prep", features_prep(False)), ("model", xgb(scale_pos_weight=spw))])}
    out = {"rows": int(len(X)), "train": int(len(Xtr)), "test": int(len(Xte)), "base_rate_train": base, "scale_pos_weight": spw, "pipelines": {}}
    best_name, best_score, best_params = None, -1.0, None
    for name, pipe in candidates.items():
        s = RandomizedSearchCV(pipe, SEARCH, n_iter=10, scoring=guarded_recall(base), cv=cv, random_state=SEED, n_jobs=1).fit(Xs, ys)
        fitted = pipe.set_params(**s.best_params_).fit(Xtr, ytr)
        out["pipelines"][name] = {"cv_guarded_recall": float(s.best_score_), "best_params": s.best_params_, "test": metrics(yte, fitted.predict_proba(Xte)[:, 1])}
        log(f"[{label}] {name:28s} CV recall {s.best_score_:.3f} | test {out['pipelines'][name]['test']}")
        if s.best_score_ > best_score:
            best_name, best_score, best_params = name, s.best_score_, s.best_params_
    for name, pipe in {"Logistic Regression (class_weight=balanced)": Pipeline([("prep", features_prep(True)), ("model", LogisticRegression(max_iter=2000, class_weight="balanced"))]),
                       "Logistic Regression + SMOTE": ImbPipeline([("prep", features_prep(True)), ("smote", SMOTE(random_state=SEED)), ("model", LogisticRegression(max_iter=2000))])}.items():
        out["pipelines"][name] = {"test": metrics(yte, pipe.fit(Xtr, ytr).predict_proba(Xte)[:, 1])}
        log(f"[{label}] {name:28s} test {out['pipelines'][name]['test']}")
    out["chosen"] = best_name
    chosen = candidates[best_name].set_params(**best_params).fit(Xtr, ytr)
    p_tr = cross_val_predict(candidates[best_name].set_params(**best_params), Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
    cuts = [float(np.quantile(p_tr, 1 / 3)), float(np.quantile(p_tr, 2 / 3))]       # three levels: tertiles of out-of-fold probabilities
    p_te = chosen.predict_proba(Xte)[:, 1]
    lv = np.where(p_te <= cuts[0], 0, np.where(p_te <= cuts[1], 1, 2))
    out["levels"] = {"cut_probabilities": cuts, "rule": "Low / Moderate / High = tertiles of out-of-fold training probabilities",
                     "test_rate_by_level": [float(yte.to_numpy()[lv == i].mean()) if (lv == i).any() else None for i in range(3)],
                     "test_share_by_level": [float((lv == i).mean()) for i in range(3)]}
    # final model on ALL rows with the chosen configuration, exported without the sampler (SMOTE only acts while training)
    refit = candidates[best_name].set_params(**best_params).fit(X, y)
    final = Pipeline([("prep", refit.named_steps["prep"]), ("model", refit.named_steps["model"])])
    return final, out


def main() -> None:
    from app.ml.spec_mileage import SpecMileageModel

    OUT.mkdir(parents=True, exist_ok=True)
    m1 = SpecMileageModel(ROOT / "backend" / "app" / "ml" / "artifacts")
    bri = brand_reliability_index()
    log(f"Brand_Reliability_Index from UK MOT outcomes: {len(bri['index'])} makes")
    d4 = d4_rates()
    D = load_d1(m1, bri, d4)
    log(f"Dataset 1 (Kaggle): {len(D):,} rows {D.file.value_counts().to_dict()}; target share {D.y.mean():.3f}; sources {SOURCE}")
    results = {"kaggle_sources": dict(SOURCE), "brand_reliability_index": bri, "dataset4_aggregation": d4,
               "dataset1": {"rows": int(len(D)), "by_file": D.file.value_counts().to_dict(), "target_share": float(D.y.mean()),
                            "excluded_file": "revised_logistics_dataset_V2.csv (contains the 92K rows of the first file + 158K noise-perturbed copies of them)",
                            "single_feature_auc": {c: float(roc_auc_score(D.y, D[c].fillna(D[c].median()))) for c in M2_NUMERIC}}}
    # monotone constraints (added, not in the PDF): more days since the last maintenance and more past failures never LOWER the score. Without them the model
    # learned an artefact of mixing the two Dataset 1 generators (failure counts of 2+ exist only in the file with the lower failure rate).
    mono = tuple(1 if c in ("days_since_last_maintenance", "failure_history") else 0 for c in M2_NUMERIC) + (0,) * len(MAINTENANCE_TYPES)
    results["ice_monotone_constraints"] = {c: 1 for c in ("days_since_last_maintenance", "failure_history")}
    ice, results["ice"] = experiment(D[M2_FEATURES], D.y, prep, search_rows=120_000, label="ICE / Dataset 1", monotone=mono)
    joblib.dump(ice, OUT / "model2_ice_pipeline.joblib", compress=3)

    # Dataset 5: dedicated electric / hybrid model, sensor columns and conditions the registry cannot give removed
    d5 = pd.read_csv(find("d5_nev", "Fault_nev_dataset.csv"))
    Xev, yev = d5[M2_EV_NUMERIC], (d5.fault_type != "no_fault").astype(int)
    ev_prep = lambda scale: ColumnTransformer([("numeric", Pipeline([("impute", SimpleImputer(strategy="median"))] + ([("scale", StandardScaler())] if scale else [])), M2_EV_NUMERIC)])
    results["ev_dataset5"] = {"single_feature_auc": {c: float(roc_auc_score(yev, Xev[c])) for c in M2_EV_NUMERIC}}
    ev, results["ev"] = experiment(Xev, yev, ev_prep, search_rows=None, label="EV / Dataset 5")
    joblib.dump(ev, OUT / "model2_ev_pipeline.joblib", compress=3)

    # external check: the ICE model on REAL inspection outcomes (UK MOT), with the inputs the API would have
    results["external_check_uk_mot"] = external_check(ice, bri, d4)
    card = {"name": "Model 2 - predictive maintenance classifier (Smart_Car_Models.pdf)", "version": "2.0.0", "trained_at": time.strftime("%Y-%m-%d"),
            "ice": {"chosen": results["ice"]["chosen"], "test": results["ice"]["pipelines"][results["ice"]["chosen"]]["test"], "levels": results["ice"]["levels"]},
            "ev": {"chosen": results["ev"]["chosen"], "test": results["ev"]["pipelines"][results["ev"]["chosen"]]["test"], "levels": results["ev"]["levels"]},
            "features_ice": M2_FEATURES, "ice_monotone_constraints": results["ice_monotone_constraints"], "features_ev": M2_EV_NUMERIC, "brand_reliability_index": bri, "dataset4_aggregation": d4,
            "medians_ice": {c: float(D[c].median()) for c in M2_NUMERIC}, "medians_ev": {c: float(Xev[c].median()) for c in M2_EV_NUMERIC},
            "external_check_uk_mot": results["external_check_uk_mot"], "kaggle_sources": dict(SOURCE)}
    (OUT / "model2_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    (ROOT / "ml" / "spec_model2_results.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    log("done")


def external_check(ice, bri: dict, d4: dict) -> dict:
    import model2_data as md2

    uk, _ = md2.uk_pairs()
    uk = uk[uk.km.notna()].sample(150_000, random_state=SEED)
    X = pd.DataFrame({"vehicle_age": uk.age_year.astype(float), "km": uk.km.astype(float), "days_since_last_maintenance": np.nan,
                      "failure_history": uk.cur_any_defect.astype(float), "brand_reliability_index": uk.make.str.lower().map(bri["index"]).fillna(bri["default"]),
                      "maintenance_type": "Unknown"}, index=uk.index)
    X = pd.concat([X, d4_features(X.km, d4)], axis=1)[M2_FEATURES]
    y = uk.next_any_defect.astype(int).to_numpy()
    p = ice.predict_proba(X)[:, 1]
    age_only = uk.age_year.map(pd.Series(y, index=uk.index).groupby(uk.age_year).mean()).to_numpy()
    out = {"pairs": int(len(uk)), "target": "a defect found at the next UK MOT inspection (real outcome)",
           "spec_model2_auc": float(roc_auc_score(y, p)), "age_only_auc": float(roc_auc_score(y, age_only)),
           "inputs": "age, true odometer, previous inspection had a defect (as failure history), brand index, Dataset 4 rates; days since maintenance unknown"}
    log(f"external check on real UK inspections: spec Model 2 AUC {out['spec_model2_auc']:.3f} vs age only {out['age_only_auc']:.3f}")
    return out


if __name__ == "__main__":
    main()
