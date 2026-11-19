"""READ-ONLY: how the covered Israeli fleet (random registry sample, scores only, no labels) distributes over the Low / Moderate / High levels of the reference scale.

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/israeli_fleet_levels.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402

ART = ROOT / "backend" / "app" / "ml" / "artifacts" / "model2"
card = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))
ref = json.loads((ART / "model2_reference.json").read_text(encoding="utf-8"))
CATS, MAKES, COLD = card["categories"], set(card["makes_in_training"]), card["variants"]["cold"]
raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
raw = raw[raw.sug_degem == "P"].copy()
il = normalise_registry(raw, reference_year=2026)
il["last"] = pd.to_datetime(raw["mivchan_acharon_dt"].to_numpy(), errors="coerce")
il["first_year"] = pd.to_numeric(pd.Series(raw["moed_aliya_lakvish"].astype(str).str.split("-").str[0].to_numpy()), errors="coerce")
il["first_year"] = il["first_year"].fillna(pd.Series(raw["shnat_yitzur"].to_numpy(), index=il.index))     # same rule as the backend
il["age_year"] = (il["last"].dt.year.fillna(2026) - il["first_year"]).astype(float)
il["make_c"] = il.make.str.title().replace({"Vauxhall": "Opel"})
il["make_c"] = il.make_c.where(il.make_c.isin(MAKES), "OTHER")
cov = il[il.fuel.isin(card["coverage"]["fuels"]) & il.age_year.between(*card["coverage"]["age_years_at_last_inspection"])].copy()
cov["gap_next"] = ref["standard_gap_years"]
X = cov[COLD].copy()
for c in ("fuel", "make_c"):
    X[c] = pd.Categorical(X[c], categories=CATS[c])
out = {"passenger_sample": int(len(il)), "covered": int(len(cov)), "share_covered": len(cov) / len(il), "levels": {}}
for s in ("brakes", "electrical", "engine_emissions"):
    b = xgb.Booster()
    b.load_model(str(ART / f"cold_{s}.json"))
    p = b.predict(xgb.DMatrix(X, enable_categorical=True))
    pct = np.interp(p, np.array(ref["reference_quantiles"][f"cold/{s}"]), np.array(ref["quantile_levels"]) * 100)
    a, c_ = ref["level_cut_percentiles"][s]
    lv = np.where(pct <= a, 0, np.where(pct <= c_, 1, 2))
    out["levels"][s] = [float((lv == i).mean()) for i in range(3)]
print(json.dumps(out, indent=1))
(ROOT / "ml" / "israeli_fleet_levels.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
