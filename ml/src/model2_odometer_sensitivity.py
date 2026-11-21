"""READ-ONLY: how robust is Model 2 to an odometer value that is NOT the true odometer at the last inspection (a mileage typed by the user)?

The odometer variants were trained with the TRUE odometer printed on the UK MOT test. A user types the CURRENT mileage: it differs from that reading by (a) the driving done since
the last inspection, (b) rounding ("about 120,000") and (c) plain mistakes. This script takes the exported models, a random sample of the UK pairs, and scores them with the true km and with
perturbed km, to see how much of the benefit of a true odometer survives. Nothing is trained or exported.
(The exported models were fitted on these pairs, so absolute AUCs are slightly optimistic; the comparison between rows is what matters.)

Run: ml/.venv/Scripts/python.exe -u -I -X utf8 ml/src/model2_odometer_sensitivity.py   (writes ml/model2_odometer_sensitivity.json)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model2_data as md2  # noqa: E402

ART = ROOT / "backend" / "app" / "ml" / "artifacts" / "model2"
card = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))
ref = json.loads((ART / "model2_reference.json").read_text(encoding="utf-8"))
CATS, MAKES, VARIANTS, SYSTEMS = card["categories"], set(card["makes_in_training"]), card["variants"], md2.SYSTEMS
rng = np.random.default_rng(0)
t0 = time.time()

uk, _ = md2.uk_pairs()
uk["make_c"] = uk.make.where(uk.make.isin(MAKES), "OTHER")
uk = uk.sample(150_000, random_state=0).reset_index(drop=True)
uk = uk[uk.km.notna() & (uk.km > 0)].reset_index(drop=True)
print(f"[{time.time()-t0:.0f}s] sample {len(uk):,} UK pairs with an odometer", flush=True)


def frame(df, cols, km=None):
    X = df[cols].copy()
    X["gap_next"] = 1.0
    if km is not None and "km" in X:
        X["km"] = km
    for c in ("fuel", "make_c"):
        X[c] = pd.Categorical(X[c], categories=CATS[c])
    return X


def score(v, s, km=None):
    b = xgb.Booster()
    b.load_model(str(ART / f"{v}_{s}.json"))
    return b.predict(xgb.DMatrix(frame(uk, VARIANTS[v], km), enable_categorical=True))


def level(v, s, p):
    q = np.array(ref["reference_quantiles"][f"{v}/{s}"])
    pct = np.interp(p, q, np.array(ref["quantile_levels"]) * 100)
    a, b = ref["level_cut_percentiles"][s]
    return np.where(pct <= a, 0, np.where(pct <= b, 1, 2))


km = uk.km.to_numpy(float)
scen = {
    "true odometer": km,
    "5% lower (a few months of driving since the test)": km * 0.95,
    "10% lower (about a year of driving since the test)": km * 0.90,
    "rounded to the nearest 10,000 km": np.round(km / 10_000) * 10_000,
    "random error +-10%": km * rng.uniform(0.9, 1.1, len(km)),
    "random error +-25%": km * rng.uniform(0.75, 1.25, len(km)),
    "random error +-50%": km * rng.uniform(0.5, 1.5, len(km)),
    "always 30% too high": km * 1.3,
    "always 50% too low": km * 0.5,
}
rows = []
for s in SYSTEMS:
    y = uk["next_" + s].to_numpy()
    for v_cold, v_odo in (("cold", "cold_odo"), ("hist", "hist_odo")):
        p_no = score(v_cold, s)
        lv_true = level(v_odo, s, score(v_odo, s, km))
        rows.append({"system": s, "variant": v_cold, "scenario": "no odometer at all", "auc": float(roc_auc_score(y, p_no)), "level_changed_vs_true_odometer": None})
        for name, k in scen.items():
            p = score(v_odo, s, k)
            rows.append({"system": s, "variant": v_odo, "scenario": name, "auc": float(roc_auc_score(y, p)), "level_changed_vs_true_odometer": float((level(v_odo, s, p) != lv_true).mean())})
    print(f"[{time.time()-t0:.0f}s] {s} done", flush=True)
(ROOT / "ml" / "model2_odometer_sensitivity.json").write_text(json.dumps({"pairs": int(len(uk)), "rows": rows}, indent=1), encoding="utf-8")
df = pd.DataFrame(rows)
pd.set_option("display.width", 220)
print(df[df.variant.isin(["cold", "cold_odo"])].assign(auc=lambda d: d.auc.round(4), level_changed_vs_true_odometer=lambda d: d.level_changed_vs_true_odometer.round(3)).to_string(index=False))
