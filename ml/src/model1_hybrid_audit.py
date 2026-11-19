"""READ-ONLY: where do the 40,000-49,000 km per year of hybrids aged 8-12 come from?  (data, learned curve, CBS calibration)

Prints, per age, the training vehicles of that fuel, the mean km of those vehicles, the yearly increment of the learned curve, the CBS age-band factor and the
calibrated yearly mileage (private ownership), for hybrid and for petrol; then the same through the current MileageModel (which is what the API serves).
Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_hybrid_audit.py <label>   (stores ml/model1_hybrid_audit.json[label])
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
import mileage_data as md  # noqa: E402
from app.ml.mileage import MileageModel  # noqa: E402

label = sys.argv[1] if len(sys.argv) > 1 else "current"
m = MileageModel(ROOT / "backend" / "app" / "ml" / "artifacts")
P = pd.concat([md.load_clean(k)[0] for k in ["d7_uk", "d8_in", "d3_cardekho"]], ignore_index=True)
age = P.age.round().astype(int)
out = {}
for fuel in ("hybrid", "petrol"):
    raw = np.maximum.accumulate(m.mean_raw[fuel])
    rows = []
    for a in range(6, 15):
        sel = (P.fuel == fuel) & (age == a)
        learned_inc = float(raw[a] - raw[a - 1])
        served = m.estimate(fuel, a, "private")
        prev = m.estimate(fuel, a - 1, "private")
        rows.append({"age": a, "training_vehicles": int(sel.sum()), "mean_km_of_those_vehicles": int(round(P.km[sel].mean(), -2)) if sel.any() else None,
                     "learned_increment_km_unsmoothed": int(round(learned_inc, -2)), "cbs_age_band_factor": round(float(m.f_age[a]), 2),
                     "served_estimate_km": served.km, "served_yearly_km": served.km - prev.km, "reliability": served.reliability})
    out[fuel] = rows
    print(fuel)
    print(pd.DataFrame(rows).to_string(index=False))
f = ROOT / "ml" / "model1_hybrid_audit.json"
store = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
store[label] = out
f.write_text(json.dumps(store, indent=1), encoding="utf-8")
