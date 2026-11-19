"""READ-ONLY (final review): coherence of the Model 2 levels on the covered Israeli fleet (scores only, no labels): levels by age group, share of makes outside the training makes
and how much the level depends on the make.

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/model2_coherence_audit.py   (writes ml/model2_coherence_audit.json)
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
il["make_known"] = il.make_c.isin(MAKES)
il["make_raw_title"] = il.make_c
il["make_c"] = il.make_c.where(il.make_known, "OTHER")
cov = il[il.fuel.isin(card["coverage"]["fuels"]) & il.age_year.between(*card["coverage"]["age_years_at_last_inspection"])].copy()
cov["gap_next"] = ref["standard_gap_years"]
X = cov[COLD].copy()
for c in ("fuel", "make_c"):
    X[c] = pd.Categorical(X[c], categories=CATS[c])
out = {"covered_vehicles": int(len(cov)), "share_make_in_training_makes": float(cov.make_known.mean())}
out["top_makes_outside_training"] = {k: int(v) for k, v in cov[~cov.make_known].make_raw_title.value_counts().head(12).items()}
groups = pd.cut(cov.age_year, [2, 5, 8, 11, 14, 20], labels=["3-5", "6-8", "9-11", "12-14", "15-20"])
out["vehicles_by_age_group"] = {str(k): int(v) for k, v in groups.value_counts().sort_index().items()}
Xo = X.copy()
Xo["make_c"] = pd.Categorical(["OTHER"] * len(Xo), categories=CATS["make_c"])
out["by_age_group"], out["spearman_age_vs_percentile"], out["level_changes_if_make_were_unknown"] = {}, {}, {}
for s in ("brakes", "electrical", "engine_emissions"):
    b = xgb.Booster()
    b.load_model(str(ART / f"cold_{s}.json"))
    a, c_ = ref["level_cut_percentiles"][s]
    q = np.array(ref["reference_quantiles"][f"cold/{s}"]); lv_of = lambda pct: np.where(pct <= a, 0, np.where(pct <= c_, 1, 2))
    pct = np.interp(b.predict(xgb.DMatrix(X, enable_categorical=True)), q, np.array(ref["quantile_levels"]) * 100)
    pct_o = np.interp(b.predict(xgb.DMatrix(Xo, enable_categorical=True)), q, np.array(ref["quantile_levels"]) * 100)
    lv = lv_of(pct)
    out["by_age_group"][s] = {str(g): [round(float((lv[(groups == g).to_numpy()] == i).mean()), 3) for i in range(3)] for g in groups.cat.categories}
    out["spearman_age_vs_percentile"][s] = round(float(pd.Series(pct).corr(pd.Series(cov.age_year.to_numpy()), method="spearman")), 3)
    kn = cov.make_known.to_numpy()
    out["level_changes_if_make_were_unknown"][s] = round(float((lv[kn] != lv_of(pct_o)[kn]).mean()), 3)
print(json.dumps(out, indent=1))
(ROOT / "ml" / "model2_coherence_audit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
