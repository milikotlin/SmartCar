"""Pair tables for the FINAL Model 2: (inspection i -> defect at the next inspection i+1 of the same vehicle).

UK  (primary, training)    : DVSA MOT, vehicle-level sample, test of year 2022 -> next test in 2023, with the true odometer at test i.
NL  (independent validation): RDW periodic inspections; consecutive inspections of the same plate; no odometer.

Only features that exist in the real system are produced:
  age_year (calendar year of inspection i minus year of first use), gap_next (planned interval to the next inspection, years),
  fuel, make, [km = measured odometer at inspection i, UK only], history flags (defect found by system at inspection i), and the targets.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_outcome_data import load_both, load_uk_veh  # noqa: E402

SYSTEMS = ["brakes", "electrical", "engine_emissions"]
FUELS = ["petrol", "diesel", "hybrid"]
AGE_RANGE = (3, 20)
MAKE_ALIAS = {"Vauxhall": "Opel"}      # the same cars: Opel in Israel and the Netherlands, Vauxhall in the UK


def _alias(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["make"] = df["make"].replace(MAKE_ALIAS)
    return df


def _finish(d: pd.DataFrame) -> pd.DataFrame:
    d = d[d.fuel.isin(FUELS) & d.age_year.between(*AGE_RANGE)].copy()
    d["unit"] = d["unit"].astype(str)
    return d.reset_index(drop=True)


def uk_pairs() -> tuple[pd.DataFrame, dict]:
    a, cut_a = load_uk_veh(2022)
    b, cut_b = load_uk_veh(2023)
    d = pd.concat([a, b]).sort_values(["unit", "date"]).reset_index(drop=True)
    g = d.groupby("unit")
    d["next_date"] = g.date.shift(-1)
    for s in SYSTEMS + ["any_defect"]:
        d["cur_" + s] = d[s]
        d["next_" + s] = g[s].shift(-1)
    d["gap_next"] = (d.next_date - d.date).dt.days / 365.25
    p = d[d.next_date.notna() & d.gap_next.between(0.5, 1.7) & (d.date.dt.year == 2022) & (d.next_date.dt.year == 2023)].copy()
    p["target_date"] = p.next_date
    p["country"] = "UK"
    p = _finish(_alias(p))
    return p, {"2022_clean_until": str(cut_a.date()), "2023_clean_until": str(cut_b.date()), "pairs": int(len(p)), "vehicles": int(p.unit.nunique())}


def nl_pairs() -> tuple[pd.DataFrame, dict]:
    _, nl = load_both()
    d = nl.sort_values(["unit", "date"]).copy()
    g = d.groupby("unit")
    d["next_date"] = g.date.shift(-1)
    for s in SYSTEMS + ["any_defect"]:
        d["cur_" + s] = d[s]
        d["next_" + s] = g[s].shift(-1)
    d["gap_next"] = (d.next_date - d.date).dt.days / 365.25
    d["km"] = np.nan
    p = d[d.next_date.notna() & (d.gap_next >= 0.5)].copy()
    p["target_date"] = p.next_date
    p["country"] = "NL"
    p = _finish(_alias(p))
    return p, {"pairs": int(len(p)), "cars": int(p.unit.nunique())}
