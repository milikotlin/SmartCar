"""Loaders + harmonisation for the Model 1 (Kilometers_Driven regression) datasets.

All sources are mapped to ONE schema:
    source, make, model, age, fuel, transmission, engine_cc, owner_count, km

Key correctness points (each one was a real bug/risk found while auditing the data):
  * UNITS: D7 (UK) `mileage` and D6 (Craigslist) `odometer` are in MILES; D8/D3 are km.
    Everything is converted to km (x1.609344).
  * AGE: odometer values are a snapshot at LISTING time, so age is computed against each
    source's own snapshot year, never against today's year.
  * DUPLICATES are removed inside each source BEFORE any train/test split (listing re-posts
    are the main leakage risk for these scraped datasets).
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR, MILES_TO_KM, RAW_DIR  # noqa: E402
from kaggle_sources import dataset_dir, find  # noqa: E402  (datasets are pulled from Kaggle with kagglehub)

COLUMNS = ["source", "make", "model", "age", "fuel", "transmission", "engine_cc", "owner_count", "km"]

# Synonyms -> canonical make (same spelling used by the backend translation + israel_registry).
MAKE_SYNONYMS = {
    "maruti": "Suzuki", "maruti suzuki": "Suzuki", "suzuki": "Suzuki",
    "mercedes": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz", "merc": "Mercedes-Benz",
    "vw": "Volkswagen", "volkswagen": "Volkswagen",
    "vauxhall": "Opel", "opel": "Opel",
    "chevy": "Chevrolet", "chevrolet": "Chevrolet",
    "bmw": "BMW", "mg": "MG", "gmc": "GMC", "ram": "Ram",
    "citroën": "Citroen", "land rover": "Land Rover", "landrover": "Land Rover",
    "alfa romeo": "Alfa Romeo", "hyundai": "Hyundai", "hyundi": "Hyundai",
}

# Fuel / transmission vocabularies -> canonical
FUEL_MAP = {
    "petrol": "petrol", "gas": "petrol", "gasoline": "petrol",
    "diesel": "diesel", "hybrid": "hybrid", "electric": "electric",
    "cng": "lpg_cng", "lpg": "lpg_cng",
}
TRANSMISSION_MAP = {"manual": "manual", "automatic": "automatic", "semi-auto": "automatic"}

# Snapshot (listing) year per source; D3 already ships vehicle_age, D6 has posting_date.
SNAPSHOT_YEAR = {"d7_uk": 2020, "d8_in": 2019}

# Cleaning thresholds
MAX_AGE = 25
MAX_KM = 500_000
MAX_KM_PER_YEAR = 100_000


def canonical_make(name) -> str | float:
    if pd.isna(name):
        return np.nan
    key = re.sub(r"\s+", " ", str(name).replace("-", " ").strip().lower())
    if key in MAKE_SYNONYMS:
        return MAKE_SYNONYMS[key]
    return key.title()


def _finish(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = df.copy()
    df["source"] = source
    df["make"] = df["make"].map(canonical_make)
    df["fuel"] = df["fuel"].astype(str).str.lower().map(FUEL_MAP)
    df["transmission"] = df["transmission"].astype(str).str.lower().map(TRANSMISSION_MAP)
    df["model"] = df["model"].astype(str).str.strip().str.lower()
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    return df[COLUMNS]


def load_d7_uk() -> pd.DataFrame:
    frames = []
    d = dataset_dir("d7_uk")
    for stem in ["audi", "bmw", "ford", "hyundi", "merc", "skoda", "toyota", "vauxhall", "vw"]:
        raw = pd.read_csv(find("d7_uk", f"{stem}.csv"))
        raw.columns = [c.strip() for c in raw.columns]
        raw["make"] = stem
        frames.append(raw)
    df = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            "make": df["make"],
            "model": df["model"],
            "age": SNAPSHOT_YEAR["d7_uk"] - df["year"],
            "fuel": df["fuelType"],
            "transmission": df["transmission"],
            "engine_cc": df["engineSize"] * 1000,
            "km": df["mileage"] * MILES_TO_KM,  # UK mileage is in MILES
        }
    )
    return _finish(out, "d7_uk")


def load_d8_in() -> pd.DataFrame:
    df = pd.concat([pd.read_csv(find("d8_in", "train-data.csv"), index_col=0), pd.read_csv(find("d8_in", "test-data.csv"), index_col=0)], ignore_index=True)
    first = df["Name"].str.split().str[0]
    make = first.where(first.str.lower() != "land", "Land Rover")
    owner = df["Owner_Type"].map({"First": 1, "Second": 2, "Third": 3, "Fourth & Above": 4})
    engine = pd.to_numeric(df["Engine"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    out = pd.DataFrame(
        {
            "make": make,
            "model": df["Name"].str.split(n=1).str[1],
            "age": SNAPSHOT_YEAR["d8_in"] - df["Year"],
            "fuel": df["Fuel_Type"],
            "transmission": df["Transmission"],
            "engine_cc": engine,
            "owner_count": owner,
            "km": df["Kilometers_Driven"],  # already km
        }
    )
    return _finish(out, "d8_in")


def load_d3_cardekho() -> pd.DataFrame:
    df = pd.read_csv(find("d3_cardekho", "cardekho_dataset.csv"), index_col=0)
    out = pd.DataFrame(
        {
            "make": df["brand"],
            "model": df["model"],
            "age": df["vehicle_age"],  # age at listing time, as shipped
            "fuel": df["fuel_type"],
            "transmission": df["transmission_type"],
            "engine_cc": df["engine"],
            "km": df["km_driven"],  # already km
        }
    )
    return _finish(out, "d3_cardekho")


def load_d6_craigslist(use_cache: bool = True) -> pd.DataFrame:
    cache = INTERIM_DIR / "d6_craigslist_slim.csv"
    if use_cache and cache.exists():
        df = pd.read_csv(cache)
    else:
        usecols = ["year", "manufacturer", "model", "fuel", "odometer", "transmission", "posting_date"]
        df = pd.read_csv(RAW_DIR / "d6_craigslist" / "vehicles.csv", usecols=usecols, low_memory=False)
        INTERIM_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache, index=False)
    posting_year = pd.to_datetime(df["posting_date"], errors="coerce", utc=True).dt.year
    out = pd.DataFrame(
        {
            "make": df["manufacturer"],
            "model": df["model"],
            "age": posting_year - df["year"],
            "fuel": df["fuel"],
            "transmission": df["transmission"],
            "km": df["odometer"] * MILES_TO_KM,  # Craigslist odometer is in MILES
        }
    )
    return _finish(out, "d6_craigslist")


LOADERS = {
    "d7_uk": load_d7_uk,
    "d8_in": load_d8_in,
    "d3_cardekho": load_d3_cardekho,
    "d6_craigslist": load_d6_craigslist,
}


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply the cleaning rules in a fixed order, returning the cleaned frame and a rule->rows-dropped log."""
    log = {"raw_rows": len(df)}

    def drop(mask, name):
        nonlocal df
        log[name] = int(mask.sum())
        df = df[~mask]

    drop(df[["make", "age", "fuel", "km"]].isna().any(axis=1), "missing make/age/fuel/km (or unmapped fuel)")
    drop((df["age"] < 0) | (df["age"] > MAX_AGE), f"age outside [0,{MAX_AGE}]")
    drop((df["km"] <= 0) | (df["km"] > MAX_KM), f"km outside (0,{MAX_KM:,}]")
    drop(df["km"] / df["age"].clip(lower=1) > MAX_KM_PER_YEAR, f"implausible rate > {MAX_KM_PER_YEAR:,} km/yr")
    drop((df["age"] >= 3) & (df["km"] < 1000), "age>=3 with <1,000 km (typo/placeholder)")
    key = ["make", "model", "age", "fuel", "transmission", "engine_cc", "km"]
    drop(df.duplicated(subset=key, keep="first"), "exact duplicate listing (all attributes + km)")
    log["clean_rows"] = len(df)
    return df.reset_index(drop=True), log


def load_clean(name: str) -> tuple[pd.DataFrame, dict]:
    return clean(LOADERS[name]())
