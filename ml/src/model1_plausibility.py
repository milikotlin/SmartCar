"""READ-ONLY: plausibility of the Model 1 estimates on the Israeli registry sample (how many vehicles get an implausible mileage?).

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model1_plausibility.py   (writes ml/model1_plausibility.json)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402
from app.ml.mileage import MileageModel  # noqa: E402

m1 = MileageModel(ROOT / "backend" / "app" / "ml" / "artifacts")
raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
raw = raw[raw.sug_degem == "P"].copy()
il = normalise_registry(raw, reference_year=2026)
il = il[il.fuel.notna()].reset_index(drop=True)
rows = []
for r in il.itertuples():
    e = m1.estimate(r.fuel, int(r.age), r.ownership)
    rows.append((e.km, e.km_low, e.km_high, e.annual_km))
il[["km", "lo", "hi", "annual"]] = rows
d = il[il.age >= 1]
out = {"vehicles_age_ge_1": int(len(d)),
       "share_estimate_above_400k_km": float((d.km > 400_000).mean()), "share_estimate_above_300k_km": float((d.km > 300_000).mean()), "share_annual_above_40k": float((d.annual > 40_000).mean()),
       "share_annual_above_35k": float((d.annual > 35_000).mean()), "max_estimate": int(d.km.max()), "max_annual": int(d.annual.max()),
       "high_range_above_500k": float((d.hi > 500_000).mean())}
bad = d[(d.km > 400_000) | (d.annual > 40_000)]
out["worst_groups"] = bad.groupby(["fuel", "ownership"]).size().sort_values(ascending=False).head(8).to_dict() if len(bad) else {}
out["worst_groups"] = {f"{k[0]}/{k[1]}": int(v) for k, v in out["worst_groups"].items()}
out["share_of_ownership_by_age_ge_8"] = {o: float((g.age >= 8).mean()) for o, g in d.groupby("ownership")}
print(json.dumps(out, indent=1))
(ROOT / "ml" / "model1_plausibility.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
