"""Writes backend/tests/fixtures/golden_model2.json: probabilities computed in the TRAINING environment (ml/.venv) with the same inference code the API uses.
The backend tests recompute them inside the API image; a difference would reveal a library or encoding mismatch between the two environments.

Usage: ml/.venv/Scripts/python.exe -I -X utf8 scripts/make_golden.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.risk import RiskInputs, RiskModel  # noqa: E402

model = RiskModel(ROOT / "backend" / "app" / "ml" / "artifacts")
none = {"brakes": False, "electrical": False, "engine_emissions": False, "any_defect": False}
brk = {"brakes": True, "electrical": False, "engine_emissions": False, "any_defect": True}
elec = {"brakes": False, "electrical": True, "engine_emissions": False, "any_defect": True}
cases = []
for age in (3, 6, 10, 15, 20):
    for fuel, make in (("petrol", "Toyota"), ("diesel", "Hyundai"), ("hybrid", "Kia"), ("petrol", "Bmw"), ("diesel", "Zeekr")):
        cases += [RiskInputs(age_year=age, gap_next=1.0, fuel=fuel, make=make),
                  RiskInputs(age_year=age, gap_next=0.85, fuel=fuel, make=make, previous=brk),
                  RiskInputs(age_year=age, gap_next=1.1, fuel=fuel, make=make, odometer_km=40_000 + 12_000 * age),
                  RiskInputs(age_year=age, gap_next=1.0, fuel=fuel, make=make, previous=elec, odometer_km=40_000 + 12_000 * age),
                  RiskInputs(age_year=age, gap_next=1.0, fuel=fuel, make=make, previous=none)]
out = []
for x in cases:
    r = model.predict(x)
    out.append({"inputs": {k: v for k, v in x.__dict__.items()}, "variant": r.variant, "probabilities": {s.system: s.probability for s in r.systems}})
dest = ROOT / "backend" / "tests" / "fixtures" / "golden_model2.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"{len(out)} golden cases -> {dest}")
