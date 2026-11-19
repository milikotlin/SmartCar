"""FINAL REVIEW fix for Model 1: smooth the learned age curve before the CBS calibration (the trained XGBoost boosters are NOT changed or retrained).

Problem found by ml/src/model1_curve_audit.py: the tree model spends the kilometres of a fuel in steps, so the calibrated yearly increment of a petrol car is
800 km at age 8 and 15,400 km at age 9, and 84,600 km for a hybrid at age 11. Consecutive ages could therefore get almost the same estimate, or jump.
Fix: a centred moving average of the yearly increments (ages 1..A_SUP, total preserved), then the same CBS raking as before on the real registry sample.
Only calibration.json (factors + `smoothing_window`) and model1_card.json (calibration section, reference points) are rewritten.

Run (no argument = compare windows and write nothing):  ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_smooth_calibration.py [--apply WINDOW]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
import calibration as cal  # noqa: E402
import cbs_reference as cbs  # noqa: E402
import mileage_data as md  # noqa: E402
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402
from app.ml.mileage import MileageModel, smooth_cumulative  # noqa: E402

ART = ROOT / "backend" / "app" / "ml" / "artifacts"
FUELS = ["diesel", "electric", "hybrid", "lpg_cng", "petrol"]


def raked(curves, il, a_sup, rates_km):
    base = cal.implied_annual(curves, il.fuel, il.age, a_sup, rates_km)
    T = {"age": {b: v[0] for b, v in cbs.CBS_AGE_2022.items()}, "own": {o: cbs.CBS_OWNERSHIP_2022[o]["all"] for o in ["private", "leasing", "company", "rental"]}}
    G = {"age": il.band.to_numpy(), "own": il.own_cbs.to_numpy()}
    factors, mult = cal.rake_means(base / 1000, G, T, ["age", "own"])
    implied = base * mult
    new = (il.age <= 3).to_numpy()
    cells = []
    for o in ["private", "leasing", "company", "rental"]:
        for grp, mask in [("new", new), ("old", ~new)]:
            m = (G["own"] == o) & mask
            if m.sum() >= 15:
                tgt = cbs.CBS_OWNERSHIP_2022[o][grp]
                cells.append({"ownership": o, "age_group": grp, "n": int(m.sum()), "model": float(implied[m].mean() / 1000), "cbs": float(tgt), "abs_pct_error": float(abs(implied[m].mean() / 1000 / tgt - 1) * 100)})
    marg = {}
    for fam in ["age", "own"]:
        for cat, tgt in T[fam].items():
            m = G[fam] == cat
            marg[f"{fam}:{cat}"] = {"n_registry_sample": int(m.sum()), "model_thousand_km_per_year": float(implied[m].mean() / 1000) if m.any() else None, "cbs_2022": float(tgt)}
    return factors, cells, marg


def lumpiness(curves, factors, a_sup, rates_km):
    """Calibrated yearly increments (private ownership factor 1) for ages 1..A_SUP+3, all fuels but electric (= petrol)."""
    f_age = np.array([factors["age"].get(cbs.age_to_band(a), 1.0) for a in range(cal.MAX_AGE + 1)])
    worst_low, worst_ratio = 1e9, 0.0
    for f in FUELS:
        if f == "electric":
            continue
        inc = cal.increments(curves[f], a_sup, rates_km) * f_age
        seg = inc[1:a_sup + 4]
        worst_low = min(worst_low, float(seg.min()))
        worst_ratio = max(worst_ratio, float(max(seg[i] / max(seg[i - 1], 1.0) for i in range(1, len(seg)))))
    return {"smallest_yearly_increment_km": round(worst_low), "largest_jump_over_previous_year": round(worst_ratio, 1)}


def main() -> None:
    apply = None
    if "--apply" in sys.argv:
        apply = int(sys.argv[sys.argv.index("--apply") + 1])
    calj = json.loads((ART / "model1" / "calibration.json").read_text(encoding="utf-8"))
    base_model = MileageModel(ART)                                                      # whatever is currently exported
    a_sup, rates_km = base_model.a_sup, np.array(calj["rates_km_by_age"])
    raw_curves = {f: np.maximum.accumulate(base_model.mean_raw[f]) for f in FUELS}      # the unsmoothed learned curves from the boosters

    il = normalise_registry(pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv"), reference_year=2026)
    il = il[il.age >= 1].reset_index(drop=True)
    il["own_cbs"] = il.ownership.map(cbs.REGISTRY_OWNERSHIP_TO_CBS)
    il["band"] = il.age.map(cbs.age_to_band)

    P = pd.concat([md.load_clean(k)[0] for k in ["d7_uk", "d8_in", "d3_cardekho"]], ignore_index=True)
    P = P[P.fuel.isin(FUELS)].reset_index(drop=True)
    age_i = P.age.round().astype(int).clip(0, cal.MAX_AGE).to_numpy()

    def fit_quality(curves):
        pred = np.zeros(len(P))
        for f in FUELS:
            m = (P.fuel == f).to_numpy()
            pred[m] = curves[f][age_i[m]]
        r = P.km.to_numpy() - pred
        return {"R2_in_sample": round(float(1 - (r ** 2).sum() / ((P.km - P.km.mean()) ** 2).sum()), 4), "RMSE_km": round(float(np.sqrt((r ** 2).mean())))}

    results = {}
    for w in (1, 3, 5):
        curves = {f: smooth_cumulative(c, a_sup, w) for f, c in raw_curves.items()}
        factors, cells, marg = raked(curves, il, a_sup, rates_km)
        results[w] = {"window": w, "joint_cell_mean_abs_pct_error": round(float(np.mean([c["abs_pct_error"] for c in cells])), 2), **lumpiness(curves, factors, a_sup, rates_km), **fit_quality(curves),
                      "_payload": (factors, cells, marg, curves)}
        print({k: v for k, v in results[w].items() if not k.startswith("_")})
    if apply is None:
        return
    factors, cells, marg, curves = results[apply]["_payload"]
    calj["age_band_factors"] = {k: float(v) for k, v in factors["age"].items()}
    calj["ownership_factors"] = {k: float(v) for k, v in factors["own"].items()}
    calj["smoothing_window"] = int(apply)
    calj["learned_curve_cumulative_km"] = {f: [float(x) for x in c] for f, c in curves.items()}
    (ART / "model1" / "calibration.json").write_text(json.dumps(calj), encoding="utf-8")

    m1 = MileageModel(ART)                                                              # reload with the new factors and smoothing
    card = json.loads((ART / "model1" / "model1_card.json").read_text(encoding="utf-8"))
    card["version"] = "1.0.1"
    card["trained_at_note"] = "boosters trained " + card["trained_at"] + " (unchanged); calibration curve smoothed in the final technical review " + time.strftime("%Y-%m-%d")
    card["calibration"].update({"marginals": marg, "held_out_joint_cells": cells, "joint_cell_mean_abs_pct_error": float(np.mean([c["abs_pct_error"] for c in cells])),
                                "smoothing": f"centred moving average of the learned yearly increments, window {apply} years (ages 1 to {a_sup}), total preserved; boosters not retrained",
                                "smoothing_comparison": {str(w): {k: v for k, v in r.items() if not k.startswith("_")} for w, r in results.items()}})
    for ref in card["reference_points"]:
        e = m1.estimate(ref["fuel"], ref["age"], ref["ownership"])
        ref["calibrated_km"] = float(e.km)
        ref["learned_uncalibrated_km"] = float(m1.curve[m1.alias.get(ref["fuel"], ref["fuel"])][ref["age"]])
    (ART / "model1" / "model1_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print("applied window", apply)


if __name__ == "__main__":
    main()
