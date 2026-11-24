"""Official REAL data used to fit the augmentation generator and, above all, to JUDGE both models (never Kaggle, never synthetic).

  UK DVSA MOT 2022 + 2023 (OGL v3.0, CRC32-verified extraction): ~1M vehicles with the true odometer; for vehicles tested in both years, the real outcome
  "a defect was found at the next inspection". NL RDW (CC0): outcomes only, a second country that is never used for fitting or selecting anything.

Every UK vehicle belongs to exactly one part, decided by a hash of its id (so both models and both years agree):
  fit 60%  - the synthetic-data generator and the brand index are fitted here;  val 20% - all choices are made here;  test 20% - opened once, at the end.
"""
import hashlib
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402
from model2_data import MAKE_ALIAS, SYSTEMS, nl_pairs  # noqa: E402
from real_outcome_data import load_uk_veh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.spec_features import make_model_key  # noqa: E402

CACHE = INTERIM_DIR / "official_uk_all.pkl"
CANON = {"Bmw": "BMW", "Mg": "MG", "Ds": "DS", "Vauxhall": "Opel"}


def part_of(unit: str) -> str:
    h = int(hashlib.md5(("smartcar:" + str(unit)).encode()).hexdigest()[:8], 16) % 100
    return "fit" if h < 60 else ("val" if h < 80 else "test")


@lru_cache(maxsize=1)
def uk_all() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    d = pd.concat([load_uk_veh(2022)[0], load_uk_veh(2023)[0]], ignore_index=True)
    d["unit"] = d.unit.astype(str)
    d["part"] = d.unit.map({u: part_of(u) for u in d.unit.unique()})
    d["model_name"] = [m[len(mk):].strip() if str(m).startswith(str(mk)) else m for m, mk in zip(d.model, d.make)]
    d["make"] = d.make.replace(CANON)
    d["make_model"] = [make_model_key(a, b) for a, b in zip(d.make, d.model_name)]
    d.to_pickle(CACHE)
    return d


def odometers() -> pd.DataFrame:
    """One row per vehicle (its earliest test): the true odometer, with the Model 1 features the MOT has. Same plausibility rules as the Kaggle listings."""
    d = uk_all().sort_values("date").drop_duplicates("unit")
    d = d[d.age_year.between(1, 25) & (d.km > 0) & (d.km <= 500_000) & (d.km / d.age_year.clip(lower=1) <= 100_000) & ~((d.age_year >= 3) & (d.km < 1000))]
    cc = d.cc.where(d.cc > 0)
    cc = cc.where(d.fuel != "electric", 0.0)                       # an electric car has no engine: 0 is a fact, not a missing value
    return pd.DataFrame({"part": d.part, "age": d.age_year.astype(int), "fuel": d.fuel, "make": d.make, "make_model": d.make_model, "engine_cc": cc,
                         "automatic": np.nan, "owner_type": "Unknown", "km": d.km}).reset_index(drop=True)


def outcome_pairs() -> pd.DataFrame:
    """(inspection 2022 -> outcome at the next inspection in 2023) for every fuel, ages 3-20. y = any defect found (real)."""
    d = uk_all().sort_values(["unit", "date"])
    g = d.groupby("unit", sort=False)
    d = d.assign(next_date=g.date.shift(-1), y=g.any_defect.shift(-1), **{f"y_{s}": g[s].shift(-1) for s in SYSTEMS})
    gap = (d.next_date - d.date).dt.days / 365.25
    p = d[d.next_date.notna() & gap.between(0.5, 1.7) & (d.date.dt.year == 2022) & (d.next_date.dt.year == 2023) & d.age_year.between(3, 20)].copy()
    return p[["unit", "part", "age_year", "fuel", "make", "make_model", "cc", "km", "any_defect", "y"] + [f"y_{s}" for s in SYSTEMS]].reset_index(drop=True).astype({"y": int})


def nl_outcomes() -> pd.DataFrame:
    """Second country, one pair per vehicle, independent of everything."""
    p, _ = nl_pairs()
    p = p.sort_values("date").drop_duplicates("unit") if "date" in p else p.drop_duplicates("unit")
    p["make"] = p.make.replace(CANON)
    p["make_model"] = [make_model_key(a, str(m)[len(str(a)):]) for a, m in zip(p.make, p.model)]
    return p.drop(columns="any_defect").rename(columns={"cur_any_defect": "any_defect", "next_any_defect": "y"})[["unit", "age_year", "fuel", "make", "make_model", "cc", "any_defect", "y"]].astype({"y": int})


if __name__ == "__main__":
    o, p, n = odometers(), outcome_pairs(), nl_outcomes()
    print("odometers", len(o), o.part.value_counts().to_dict(), o.fuel.value_counts().to_dict())
    print("pairs", len(p), p.part.value_counts().to_dict(), p.fuel.value_counts().to_dict(), "base", round(p.y.mean(), 3))
    print("NL", len(n), "base", round(n.y.mean(), 3))
