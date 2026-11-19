"""READ-ONLY audit of the Model 1 calibrated curve: yearly increments, kinks, interval shape, electric and very old vehicles.

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_curve_audit.py   (writes ml/model1_curve_audit.json)
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.mileage import MileageModel  # noqa: E402

m = MileageModel(ROOT / "backend" / "app" / "ml" / "artifacts")
out = {"a_sup": m.a_sup, "max_age": m.max_age, "f_age": {int(a): round(float(m.f_age[a]), 3) for a in (0, 3, 4, 6, 7, 9, 10, 13, 14, 19, 20, 30)}}
report = {}
for fuel in ("petrol", "diesel", "hybrid", "lpg_cng", "electric"):
    key = m.alias.get(fuel, fuel)
    cal = m._calibrated_curve(key)
    inc = np.r_[cal[0], np.diff(cal)]
    learned_inc = np.r_[m.curve[key][0], np.diff(m.curve[key])]
    est = [m.estimate(fuel, a, "private") for a in range(0, 46)]
    low_inc = [(a, int(round(inc[a], -2))) for a in range(1, 31) if inc[a] < 3000]       # implausibly low yearly mileage
    jumps = [(a, int(round(inc[a], -2)), int(round(inc[a - 1], -2))) for a in range(2, 31) if inc[a] > 1.8 * inc[a - 1] and inc[a - 1] > 0]
    width = {a: round((est[a].km_high - est[a].km_low) / max(est[a].km, 1), 2) for a in (1, 3, 5, 8, 11, 14, 20, 30)}
    report[fuel] = {"yearly_increment_km_ages_1_to_16": [int(round(inc[a], -2)) for a in range(1, 17)],
                    "years_with_increment_below_3000_km": low_inc, "years_with_jump_above_1.8x_previous": jumps,
                    "monotone_km": bool(all(est[a + 1].km >= est[a].km for a in range(45))),
                    "interval_width_over_estimate": width,
                    "low_le_est_le_high": bool(all(e.km_low <= e.km <= e.km_high for e in est))}
out["by_fuel"] = report
# ownership spread at one age and the very old tail
out["ownership_spread_petrol_age_8"] = {o: m.estimate("petrol", 8, o).km for o in ("private", "leasing", "company", "rental", "dealer", None)}
out["very_old_petrol_private"] = {a: (m.estimate("petrol", a, "private").km, m.estimate("petrol", a, "private").annual_km) for a in (13, 14, 20, 30, 40, 45, 60)}
out["electric_vs_petrol_same"] = bool(all(m.estimate("electric", a, "private").km == m.estimate("petrol", a, "private").km for a in range(0, 30)))
print(json.dumps(out, indent=1))
(ROOT / "ml" / "model1_curve_audit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
