"""Loaders that turn the two REAL-OUTCOME samples into one harmonised table each (experiments only).

UK  : DVSA MOT (OGL v3.0)   -> tests 1 Jan - 26 Jun 2023, class 4 (cars), normal test. Odometer exists.
NL  : RDW open data (CC0)   -> periodic inspections (APK) of passenger cars whose plate ends in K. No odometer.

Common columns: country, unit (vehicle id / plate), date, age_year (calendar year of test minus year of first use/admission),
fuel (petrol/diesel/hybrid/electric/lpg_cng), make, model ("<make> <model>", title case), cc, mass, km (UK only),
brakes, electrical, engine_emissions, any_defect (0/1 per inspection: at least one defect of that system was recorded).

The system mapping is the same as in notebooks 04 (UK) and 05 (NL). Outcome = defect FOUND AT AN INSPECTION, not a breakdown.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from config import INTERIM_DIR, RAW_DIR

CLEAN_ITEM_ROWS = 801_511        # UK items stream is readable only up to here (see notebook 04, "known limitation")
UK_LAST_DATE = "2023-06-27"       # exclusive upper bound of the readable part of the UK sample


def load_uk(year: int = 2023) -> pd.DataFrame:
    res = pd.read_csv(INTERIM_DIR / f"uk_mot_{year}_results_sample.csv", sep="|", low_memory=False, on_bad_lines="skip", dtype=str)
    res = res[res.test_id.str.fullmatch(r"\d+")].copy()
    res["test_id"] = res.test_id.astype("int64")
    res = res[res.test_id % 41 == 0]                     # sampling rule: damaged remnants fail this check
    for c in ["vehicle_id", "test_mileage", "cylinder_capacity"]:
        res[c] = pd.to_numeric(res[c], errors="coerce")
    res = res[(res.test_class_id == "4") & (res.test_type == "NT") & res.vehicle_id.notna()].drop_duplicates("test_id")
    res = res[res.test_date < UK_LAST_DATE]
    items = pd.read_csv(INTERIM_DIR / f"uk_mot_{year}_items_sample.csv", sep="|", low_memory=False, on_bad_lines="skip", dtype=str, nrows=CLEAN_ITEM_ROWS)
    items = items[items.test_id.str.fullmatch(r"\d+") & items.rfr_id.str.fullmatch(r"\d+")].copy()
    items["test_id"] = items.test_id.astype("int64")
    items["rfr_id"] = items.rfr_id.astype("int64")
    items = items[items.test_id.isin(set(res.test_id))]
    det = pd.read_csv(RAW_DIR / "uk_mot_lookup" / "dft_item_detail_extract.csv")
    rfr2sec = det[det.test_class_id == 4].drop_duplicates("rfr_id").set_index("rfr_id").test_item_set_section_id
    items["section"] = items.rfr_id.map(rfr2sec)
    SYSTEM = {5430: "brakes", 20003: "brakes", 5000: "electrical", 20158: "electrical", 5730: "engine_emissions", 20385: "engine_emissions"}
    items["system"] = items.section.map(SYSTEM).fillna("other")
    defects = items[items.rfr_type_code.isin(["F", "P"])]

    d = res.copy()
    d["date"] = pd.to_datetime(d.test_date, errors="coerce")
    d["first"] = pd.to_datetime(d.first_use_date, errors="coerce")
    d["age_year"] = d.date.dt.year - d["first"].dt.year
    d["age"] = (d.date - d["first"]).dt.days / 365.25
    d = d[d.test_mileage.between(1, 600_000) & d.age.between(0, 30)]
    FUEL = {"PE": "petrol", "DI": "diesel", "HY": "hybrid", "EL": "electric", "LP": "lpg_cng", "CN": "lpg_cng", "GB": "lpg_cng", "GA": "lpg_cng"}
    d["fuel"] = d.fuel_type.map(FUEL).fillna("other")
    d = d[d.fuel != "other"]
    d["make"] = d.make.str.title()
    d["model"] = d.make + " " + d.model.astype(str).str.title()
    d["km"] = d.test_mileage * 1.609344                  # UK odometers are in miles
    d["cc"] = pd.to_numeric(d.cylinder_capacity, errors="coerce")
    d["mass"] = np.nan
    for s in ["brakes", "electrical", "engine_emissions"]:
        d[s] = d.test_id.isin(set(defects[defects.system == s].test_id)).astype(int)
    d["any_defect"] = d.test_id.isin(set(defects.test_id)).astype(int)
    d["unit"] = d.vehicle_id.astype("int64")
    d["country"] = "UK"
    return d[["country", "unit", "date", "age_year", "age", "fuel", "make", "model", "cc", "mass", "km", "brakes", "electrical", "engine_emissions", "any_defect"]].reset_index(drop=True)


def _nl_system_of(article: str) -> str:
    a = str(article)
    m = re.match(r"^5\.\*\.(\d+)([a-zA-Z]?)$", a)
    if m:
        n = int(m.group(1))
        if 31 <= n <= 40:
            return "brakes"
        if 51 <= n <= 65 or n == 12 or n == 71:
            return "electrical"
        if n in (9, 10, 11, 13):
            return "engine_emissions"
    if a in ("RA6", "RA7", "AC5"):
        return "brakes"
    return "other"


def load_nl() -> pd.DataFrame:
    import json
    load = lambda n: pd.DataFrame(json.loads((INTERIM_DIR / n).read_text(encoding="utf-8")))
    reg, fuel, tests, defects, cat = load("nl_registry_K.json"), load("nl_fuel_K.json"), load("nl_tests_K.json"), load("nl_defects_K.json"), load("nl_defect_catalogue.json")
    cat["system"] = cat.gebrek_artikel_nummer.map(_nl_system_of)
    id2sys = cat.drop_duplicates("gebrek_identificatie").set_index("gebrek_identificatie").system
    defects["system"] = defects.gebrek_identificatie.map(id2sys).fillna("other")
    defects["n"] = pd.to_numeric(defects.aantal_gebreken_geconstateerd, errors="coerce").fillna(1)

    t = tests[tests.soort_melding_ki_omschrijving == "periodieke controle"].copy()
    t["date"] = pd.to_datetime(t.meld_datum_door_keuringsinstantie, format="%Y%m%d", errors="coerce")
    t = t.dropna(subset=["date"]).drop_duplicates(["kenteken", "date"]).sort_values(["kenteken", "date"])
    t["gap"] = t.groupby("kenteken").date.diff().dt.days
    t = t[~(t.gap < 60)].copy()                           # drop probable re-inspections
    defects["date"] = pd.to_datetime(defects.meld_datum_door_keuringsinstantie, format="%Y%m%d", errors="coerce")
    dd = defects.groupby(["kenteken", "date", "system"]).n.sum().unstack(fill_value=0)
    t = t.merge(dd.reset_index(), on=["kenteken", "date"], how="left")
    for s in ["brakes", "electrical", "engine_emissions", "other"]:
        t[s] = (t.get(s).fillna(0) > 0).astype(int)
    t["any_defect"] = (t[["brakes", "electrical", "engine_emissions", "other"]].sum(axis=1) > 0).astype(int)

    reg = reg.drop_duplicates("kenteken")
    reg["first"] = pd.to_datetime(reg.datum_eerste_toelating, format="%Y%m%d", errors="coerce")
    fu = fuel.copy()
    fu["vn"] = pd.to_numeric(fu.brandstof_volgnummer, errors="coerce")
    elec = set(fu[fu.brandstof_omschrijving.str.lower().isin(["elektriciteit"])].kenteken)
    nfuel = fu.groupby("kenteken").size()
    prim = fu.sort_values("vn").drop_duplicates("kenteken").set_index("kenteken").brandstof_omschrijving.str.lower()
    FMAP = {"benzine": "petrol", "diesel": "diesel", "lpg": "lpg_cng", "cng": "lpg_cng", "elektriciteit": "electric", "alcohol": "other", "waterstof": "other"}
    reg["fuel"] = reg.kenteken.map(prim).map(FMAP).fillna("other")
    hyb = reg.kenteken.map(nfuel).fillna(1).gt(1) & reg.kenteken.isin(elec) & (reg.fuel != "electric")
    reg.loc[hyb, "fuel"] = "hybrid"
    d = t.merge(reg[["kenteken", "merk", "handelsbenaming", "first", "fuel", "cilinderinhoud", "massa_rijklaar", "taxi_indicator"]], on="kenteken", how="inner")
    d["age_year"] = d.date.dt.year - d["first"].dt.year
    d["age"] = (d.date - d["first"]).dt.days / 365.25
    d = d[d.age_year.between(3, 30) & d.fuel.isin(["petrol", "diesel", "hybrid", "electric", "lpg_cng"]) & d.merk.notna() & (d.taxi_indicator != "Ja")]
    d["make"] = d.merk.str.title()
    d["model"] = d.make + " " + d.handelsbenaming.fillna("?").str.title()
    d["cc"] = pd.to_numeric(d.cilinderinhoud, errors="coerce")
    d["mass"] = pd.to_numeric(d.massa_rijklaar, errors="coerce")
    d["km"] = np.nan
    d["unit"] = d.kenteken
    d["country"] = "NL"
    return d[["country", "unit", "date", "age_year", "age", "fuel", "make", "model", "cc", "mass", "km", "brakes", "electrical", "engine_emissions", "any_defect"]].reset_index(drop=True)


def load_both(cache: bool = True):
    p = INTERIM_DIR / "harmonised_uk_nl.pkl"
    if cache and p.exists():
        return pd.read_pickle(p)
    out = (load_uk(), load_nl())
    if cache:
        pd.to_pickle(out, p)
    return out
