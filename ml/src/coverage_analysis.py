"""READ-ONLY: why vehicles fall outside Model 2's coverage, on a random sample of the Israeli registry (19,200 passenger vehicles).

Run: ml/.venv/Scripts/python.exe -I -X utf8 ml/src/coverage_analysis.py   (writes ml/coverage_analysis.json)
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402
from israel_registry import normalise_registry  # noqa: E402

card = json.loads((ROOT / "backend" / "app" / "ml" / "artifacts" / "model2" / "model2_card.json").read_text(encoding="utf-8"))
lo, hi = card["coverage"]["age_years_at_last_inspection"]
fuels = card["coverage"]["fuels"]
raw = pd.read_csv(INTERIM_DIR / "gov_registry_sample.csv")
raw = raw[raw.sug_degem == "P"].copy()
il = normalise_registry(raw, reference_year=2026)
il["last"] = pd.to_datetime(raw["mivchan_acharon_dt"].to_numpy(), errors="coerce")
il["first_year"] = pd.to_numeric(pd.Series(raw["moed_aliya_lakvish"].astype(str).str.split("-").str[0].to_numpy()), errors="coerce")
# same rules as the backend: first-registration year when present, else the manufacture year; the current year when the last test date is missing
il["first_year"] = il["first_year"].fillna(pd.Series(raw["shnat_yitzur"].to_numpy(), index=il.index))
il["age_year"] = (il["last"].dt.year.fillna(2026) - il["first_year"]).astype(float)
il["manuf_age"] = 2026 - raw["shnat_yitzur"].to_numpy()
n = len(il)
bad_fuel = ~il.fuel.isin(fuels)
young = il.age_year < lo
old = il.age_year > hi
missing = il.age_year.isna()
covered = ~bad_fuel & ~young & ~old & ~missing


def share(m):
    return float(m.mean())


out = {
    "sample": int(n), "covered": share(covered),
    "not_covered_total": 1 - share(covered),
    "by_reason_exclusive_first_match": {
        "age below 3 at the last inspection (first annual test not yet taken)": share(young & ~missing),
        "age above 20": share(old & ~young),
        "electric or gas fuel (age within 3-20)": share(bad_fuel & ~young & ~old & ~missing),
        "missing dates": share(missing),
    },
    "any_reason": {"fuel not covered": share(bad_fuel), "age below 3": share(young), "age above 20": share(old)},
    "fuel_mix_of_uncovered_fuel": il.fuel[bad_fuel].value_counts(normalize=True).to_dict(),
    "age_at_last_inspection_of_young_group": il.age_year[young].value_counts(normalize=True).sort_index().to_dict(),
    "share_of_young_group_that_is_electric_or_gas": share(bad_fuel[young]),
    "electric_share_by_manufacture_year_2022_2026": {int(y): float((il.fuel[raw["shnat_yitzur"].to_numpy() == y] == "electric").mean()) for y in range(2022, 2027)},
    "would_be_covered_if_new_cars_were_added": share(covered | (young & ~bad_fuel & ~missing)),
    "would_be_covered_if_electric_were_added_within_age_3_20": share(covered | (bad_fuel & il.fuel.eq("electric") & ~young & ~old & ~missing)),
}
print(json.dumps(out, indent=1))
(ROOT / "ml" / "coverage_analysis.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
