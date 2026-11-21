"""Model 1 (odometer regression) EXACTLY as Smart_Car_Models.pdf specifies, with the data pulled from Kaggle (kagglehub).

Specification -> implementation
  * Data fusion: Dataset 7 (UK, backbone), Dataset 8 (adds Owner_Type), Dataset 3 (Cardekho)        -> mileage_data.py loaders, pd.concat
  * Schema alignment: units ("CC" removed, UK miles -> km), standard fuel vocabulary, pd.concat       -> mileage_data.py
  * OHE for low-cardinality columns (fuel, transmission, ownership type)                              -> OneHotEncoder (transmission is binary: one 0/1 column)
  * Make/Model: Target Encoding vs Frequency Encoding, chosen by cross-validation                     -> experiment 1 (5-fold CV, XGBoost held fixed)
  * Missing values: KNN Imputer, K=5 (engine size, transmission)                                     -> KNNImputer(n_neighbors=5)
  * Algorithms: Linear/Ridge (StandardScaler or MinMaxScaler) vs Random Forest / XGBoost (no scaling) -> experiment 2
  * Final model chosen purely by RMSE and MAE                                                         -> lowest cross-validated RMSE (MAE breaks ties)
Added (documented, not in the PDF): CBS calibration to the official Israeli level, 80% range from held-out residuals, low-reliability flags.

Note found while implementing: Dataset 8 `Owner_Type` is the NUMBER of owners (First / Second / Third / Fourth & Above), not private / leasing / company as
the PDF says. It is used as such; at run time it comes from the ownership history of the Ministry of Transport (app/services/vehicle_specs.py: one row per ownership,
'Unknown' for cars older than that table).

Run:  ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/spec_model1.py
Writes backend/app/ml/artifacts/spec/model1_pipeline.joblib, model1_calibration.json, model1_card.json and ml/spec_model1_results.json.
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import KNNImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, StandardScaler, TargetEncoder
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
import calibration as cal  # noqa: E402
import cbs_reference as cbs  # noqa: E402
import mileage_data as md  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402
from kaggle_sources import SOURCE  # noqa: E402
from app.ml.spec_features import M1_FEATURES, M1_HIGH_CARD, M1_LOW_CARD, M1_NUMERIC, FrequencyEncoder, make_model_key, owner_type  # noqa: E402

OUT = ROOT / "backend" / "app" / "ml" / "artifacts" / "spec"
SEED = 42
MIN_ROWS_PER_AGE = 30
t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:5.0f}s] {msg}", flush=True)


# ------------------------------------------------------------------ data (Kaggle) + schema alignment
def load() -> pd.DataFrame:
    frames = [md.load_clean(k)[0] for k in ("d7_uk", "d8_in", "d3_cardekho")]
    P = pd.concat(frames, ignore_index=True)
    P["engine_cc"] = P["engine_cc"].where(P["engine_cc"] > 0)                  # 0 = not given (electric / missing) -> imputed
    P["automatic"] = P["transmission"].map({"automatic": 1.0, "manual": 0.0})
    P["owner_type"] = P["owner_count"].map(owner_type)
    P["make_model"] = [make_model_key(a, b) for a, b in zip(P["make"], P["model"])]
    return P


def preprocessor(encoding: str, scaler=None) -> ColumnTransformer:
    numeric = [("impute", KNNImputer(n_neighbors=5))] + ([("scale", scaler)] if scaler is not None else [])
    high = TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=SEED)) if encoding == "target" else FrequencyEncoder()
    high_steps = [("encode", high)] + ([("scale", StandardScaler() if isinstance(scaler, StandardScaler) else MinMaxScaler())] if scaler is not None else [])
    return ColumnTransformer([
        ("numeric", Pipeline(numeric), M1_NUMERIC),
        ("low_card", OneHotEncoder(handle_unknown="ignore", sparse_output=False), M1_LOW_CARD),
        ("make_model", Pipeline(high_steps), M1_HIGH_CARD),
    ])


def xgb() -> XGBRegressor:
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8, tree_method="hist", n_jobs=8, random_state=SEED)


ALGORITHMS = {
    "Linear Regression + StandardScaler": (lambda: LinearRegression(), StandardScaler),
    "Ridge + StandardScaler": (lambda: Ridge(alpha=1.0), StandardScaler),
    "Ridge + MinMaxScaler": (lambda: Ridge(alpha=1.0), MinMaxScaler),
    "Random Forest (no scaling)": (lambda: RandomForestRegressor(n_estimators=150, min_samples_leaf=5, max_features=0.6, n_jobs=8, random_state=SEED), None),
    "XGBoost (no scaling)": (xgb, None),
}


def cv_scores(pipe, X, y) -> dict:
    s = cross_validate(pipe, X, y, cv=KFold(5, shuffle=True, random_state=SEED), scoring=("neg_root_mean_squared_error", "neg_mean_absolute_error"), n_jobs=1)
    return {"cv_rmse": float(-s["test_neg_root_mean_squared_error"].mean()), "cv_mae": float(-s["test_neg_mean_absolute_error"].mean()),
            "cv_rmse_sd": float(s["test_neg_root_mean_squared_error"].std())}


def held_out(pipe, Xtr, ytr, Xte, yte) -> dict:
    p = np.clip(pipe.fit(Xtr, ytr).predict(Xte), 0, None)
    r = yte.to_numpy() - p
    return {"test_rmse": float(np.sqrt(np.mean(r ** 2))), "test_mae": float(np.mean(np.abs(r))), "test_r2": float(1 - np.sum(r ** 2) / np.sum((yte - yte.mean()) ** 2))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    P = load()
    log(f"Datasets 7+8+3 from Kaggle: {len(P):,} rows {P.source.value_counts().to_dict()}; sources {SOURCE}")
    X, y = P[M1_FEATURES], P["km"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=P["source"])
    results = {"rows": int(len(P)), "rows_by_dataset": P.source.value_counts().to_dict(), "kaggle_sources": dict(SOURCE),
               "missing_share": {c: float(P[c].isna().mean()) for c in ("engine_cc", "automatic")},
               "make_model_categories": int(P.make_model.nunique())}

    # --- experiment 1: Target vs Frequency encoding of Make/Model (cross-validation, algorithm held fixed)
    enc = {}
    for name in ("target", "frequency"):
        enc[name] = cv_scores(Pipeline([("prep", preprocessor(name)), ("model", xgb())]), Xtr, ytr)
        log(f"encoding {name}: CV RMSE {enc[name]['cv_rmse']:,.0f}  MAE {enc[name]['cv_mae']:,.0f}")
    best_enc = min(enc, key=lambda k: (enc[k]["cv_rmse"], enc[k]["cv_mae"]))
    results["experiment_1_encoding"] = {"scores": enc, "chosen": best_enc}

    # --- experiment 2: algorithms (and scalers for the linear models), with the chosen encoding
    alg = {}
    for name, (make, scaler) in ALGORITHMS.items():
        pipe = Pipeline([("prep", preprocessor(best_enc, scaler() if scaler else None)), ("model", make())])
        alg[name] = {**cv_scores(pipe, Xtr, ytr), **held_out(pipe, Xtr, ytr, Xte, yte)}
        log(f"{name:36s} CV RMSE {alg[name]['cv_rmse']:,.0f}  MAE {alg[name]['cv_mae']:,.0f} | held-out RMSE {alg[name]['test_rmse']:,.0f}  MAE {alg[name]['test_mae']:,.0f}  R2 {alg[name]['test_r2']:.3f}")
    best_alg = min(alg, key=lambda k: (alg[k]["cv_rmse"], alg[k]["cv_mae"]))
    results["experiment_2_algorithms"] = {"scores": alg, "chosen": best_alg, "rule": "lowest cross-validated RMSE, MAE breaks ties"}
    make, scaler = ALGORITHMS[best_alg]

    # --- residual ratios on held-out vehicles (for the indicative 80% range), then the final model on ALL rows
    pipe = Pipeline([("prep", preprocessor(best_enc, scaler() if scaler else None)), ("model", make())])
    p_te = np.clip(pipe.fit(Xtr, ytr).predict(Xte), 1, None)
    ratio = yte.to_numpy() / p_te
    bands, labels = cbs.AGE_BANDS, cbs.BAND_LABELS
    te_band = Xte["age"].map(cbs.age_to_band).to_numpy()
    ratio_q = {b: [float(np.quantile(ratio[te_band == b], 0.1)), float(np.quantile(ratio[te_band == b], 0.9))] if (te_band == b).sum() >= 50 else [float(np.quantile(ratio, 0.1)), float(np.quantile(ratio, 0.9))]
               for b in labels}
    cover = float(np.mean((yte.to_numpy() >= p_te * np.array([ratio_q[b][0] for b in te_band])) & (yte.to_numpy() <= p_te * np.array([ratio_q[b][1] for b in te_band]))))
    results["interval_80pct_heldout_coverage"] = cover
    final = Pipeline([("prep", preprocessor(best_enc, scaler() if scaler else None)), ("model", make())]).fit(X, y)
    joblib.dump(final, OUT / "model1_pipeline.joblib", compress=3)
    log(f"final model: {best_alg} with {best_enc} encoding, trained on all {len(P):,} rows; 80% range covers {cover:.1%} of held-out vehicles")

    # --- support per fuel and age (low-reliability flags) and the age above which the data carry no information
    age_i = P["age"].round().astype(int)
    a_sup = cal.supported_max_age(P["age"])
    support = {}
    for f in ("diesel", "hybrid", "lpg_cng"):
        a = 3
        while a <= cal.MAX_AGE and ((P.fuel == f) & (age_i == a)).sum() >= MIN_ROWS_PER_AGE:
            a += 1
        if a - 1 < a_sup:
            support[f] = a - 1
    rates22 = {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}
    base_cal = {"max_age": cal.MAX_AGE, "a_sup": int(a_sup), "smoothing_window": 3, "support_max_age": support, "min_training_vehicles_per_age": MIN_ROWS_PER_AGE,
                "rates_km_by_age": [float(rates22[cbs.age_to_band(a)] * 1000) for a in range(cal.MAX_AGE + 1)],
                "age_bands": [list(b) for b in bands], "age_band_labels": labels, "age_band_factors": {b: 1.0 for b in labels},
                "ownership_factors": {o: 1.0 for o in ("private", "leasing", "company", "rental")}, "registry_ownership_to_cbs": cbs.REGISTRY_OWNERSHIP_TO_CBS,
                "residual_ratio_quantiles": ratio_q,
                "cbs_ownership_all_thousand_km": {o: cbs.CBS_OWNERSHIP_2022[o]["all"] for o in ("private", "leasing", "company", "rental")},
                "cbs_fleet_mean_thousand_km": cbs.CBS_OWNERSHIP_2022["total"]["all"]}
    (OUT / "model1_calibration.json").write_text(json.dumps(base_cal), encoding="utf-8")       # uncalibrated placeholder; calibrate() below replaces it
    results["support_max_age"], results["a_sup"] = support, int(a_sup)
    calibrate(base_cal, results)
    (ROOT / "ml" / "spec_model1_results.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    write_card(results)
    log("done")


def write_card(results: dict) -> None:
    """Model card read by the API and the tests (backend/app/ml/artifacts/spec/model1_card.json)."""
    e1, e2 = results.get("experiment_1_encoding", {}), results.get("experiment_2_algorithms", {})
    card = {"name": "Model 1 - odometer regression (Smart_Car_Models.pdf)", "version": "2.0.0", "trained_at": time.strftime("%Y-%m-%d"),
            "kaggle_sources": results.get("kaggle_sources"), "rows": results.get("rows"), "rows_by_dataset": results.get("rows_by_dataset"),
            "features": M1_FEATURES, "encoding_experiment": e1, "algorithm_experiment": e2,
            "chosen": {"encoding": e1.get("chosen"), "algorithm": e2.get("chosen"), "held_out": (e2.get("scores") or {}).get(e2.get("chosen"), {})},
            "interval_80pct_heldout_coverage": results.get("interval_80pct_heldout_coverage"), "support_max_age": results.get("support_max_age"),
            "a_sup": results.get("a_sup"), "calibration": results.get("calibration"),
            "registry_sample_with_official_engine_data": results.get("registry_sample_with_official_engine_data"),
            "note_owner_type": "Dataset 8 Owner_Type is the number of owners (First / Second / Third / Fourth & Above), not private / leasing as the PDF says"}
    (OUT / "model1_card.json").write_text(json.dumps(card, indent=1, default=str), encoding="utf-8")


def registry_features() -> tuple[pd.DataFrame, list[dict]]:
    """The real Israeli registry sample with the Model 1 features as the API builds them (engine size and transmission from the official model table)."""
    raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
    raw = raw[raw.sug_degem == "P"].copy()
    il = normalise_registry(raw, reference_year=2026)
    il["tozeret_cd"], il["degem_cd"], il["shnat_yitzur"], il["kinuy"] = raw["tozeret_cd"].to_numpy(), raw["degem_cd"].to_numpy(), raw["shnat_yitzur"].to_numpy(), raw["kinuy_mishari"].to_numpy()
    wltp_path = INTERIM_DIR / "wltp_models.csv"
    if wltp_path.exists():
        w = pd.read_csv(wltp_path).drop_duplicates(["tozeret_cd", "degem_cd", "shnat_yitzur"])
        il = il.merge(w[["tozeret_cd", "degem_cd", "shnat_yitzur", "nefah_manoa", "automatic_ind"]], on=["tozeret_cd", "degem_cd", "shnat_yitzur"], how="left")
    else:
        il["nefah_manoa"], il["automatic_ind"] = np.nan, np.nan
    il = il[il.fuel.notna() & (il.age >= 1)].reset_index(drop=True)
    feats = [{"age": int(r.age), "engine_cc": r.nefah_manoa if pd.notna(r.nefah_manoa) else None, "automatic": float(r.automatic_ind) if pd.notna(r.automatic_ind) else None,
              "fuel": r.fuel, "owner_type": "Unknown", "make_model": make_model_key(r.make, r.kinuy)} for r in il.itertuples()]
    return il, feats


def calibrate(base_cal: dict, results: dict) -> None:
    """Same CBS raking as before (age band x ownership), on the yearly increments of each registry vehicle's own predicted path."""
    from app.ml.spec_mileage import SpecMileageModel

    m = SpecMileageModel(ROOT / "backend" / "app" / "ml" / "artifacts", calibration=base_cal)
    il, feats = registry_features()
    results["registry_sample_with_official_engine_data"] = float(np.mean([f["engine_cc"] is not None for f in feats]))
    inc_at_age = np.array([m.calibrated_increments(f)[min(f["age"], m.max_age)] for f in feats])
    il["own_cbs"], il["band"] = il.ownership.map(cbs.REGISTRY_OWNERSHIP_TO_CBS), il.age.map(cbs.age_to_band)
    T = {"age": {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}, "own": {o: cbs.CBS_OWNERSHIP_2022[o]["all"] for o in ["private", "leasing", "company", "rental"]}}
    G = {"age": il.band.to_numpy(), "own": il.own_cbs.to_numpy()}
    factors, mult = cal.rake_means(inc_at_age / 1000, G, T, ["age", "own"])
    implied = inc_at_age * mult
    new = (il.age <= 3).to_numpy()
    cells = []
    for o in ["private", "leasing", "company", "rental"]:
        for grp, mask in [("new", new), ("old", ~new)]:
            sel = (G["own"] == o) & mask
            if sel.sum() >= 15:
                tgt = cbs.CBS_OWNERSHIP_2022[o][grp]
                cells.append({"ownership": o, "age_group": grp, "n": int(sel.sum()), "model": float(implied[sel].mean() / 1000), "cbs": float(tgt),
                              "abs_pct_error": float(abs(implied[sel].mean() / 1000 / tgt - 1) * 100)})
    final_cal = {**base_cal, "age_band_factors": {k: float(v) for k, v in factors["age"].items()}, "ownership_factors": {k: float(v) for k, v in factors["own"].items()}}
    (OUT / "model1_calibration.json").write_text(json.dumps(final_cal), encoding="utf-8")
    results["calibration"] = {"source": "CBS Publication 1923, Tables 4 and 8", "registry_sample_rows": int(len(il)), "factors": factors,
                              "held_out_joint_cells": cells, "joint_cell_mean_abs_pct_error": float(np.mean([c["abs_pct_error"] for c in cells])) if cells else None}
    log(f"CBS calibration on {len(il):,} registry vehicles (official engine data for {results['registry_sample_with_official_engine_data']:.0%}); "
        f"held-out CBS joint-cell error {results['calibration']['joint_cell_mean_abs_pct_error']:.1f}%")


if __name__ == "__main__":
    if "--calibrate-only" in sys.argv:          # after fetch_wltp.py, recalibrate the exported model without retraining it
        base = json.loads((OUT / "model1_calibration.json").read_text(encoding="utf-8"))
        base.update({"age_band_factors": {b: 1.0 for b in base["age_band_labels"]}, "ownership_factors": {o: 1.0 for o in base["ownership_factors"]}})
        res_path = ROOT / "ml" / "spec_model1_results.json"
        res = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
        calibrate(base, res)
        res_path.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        write_card(res)
    else:
        main()
