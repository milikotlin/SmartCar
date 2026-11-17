"""
Stage 1 - Regression model: imputes Kilometers_Driven from features available
at inference time (Make, Vehicle_Age, Fuel_Type, Ownership - i.e. exactly what
the Gov API gives us after translation).

Data sources (substituting the SRS's "Kaggle Dataset 8 / Dataset 7" references,
which pointed to a numbered course list we didn't have access to):
  - "Vehicle dataset from cardekho" (nehalbirla) -> car details v4.csv
    https://www.kaggle.com/datasets/nehalbirla/vehicle-dataset-from-cardekho
  - "100,000 UK Used Car Data Set" (adityadesai13) -> audi/bmw/ford/... .csv
    https://www.kaggle.com/datasets/adityadesai13/used-car-dataset-ford-and-mercedes
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# The odometer readings in each dataset reflect the mileage AT THE TIME THAT
# LISTING WAS SCRAPED, not today. Vehicle_Age must therefore be computed
# against each source's own snapshot year, or the age<->mileage relationship
# gets distorted (a "2020" UK listing has near-zero mileage because it was
# scraped in 2020, not because it is a brand-new car today).
#   - UK "100,000 UK Used Car" dataset: files dated Jul 2020 -> scraped ~2020.
#   - CarDekho "car details v4": file dated Jan 2023 -> scraped ~2022/2023.
SOURCE_SNAPSHOT_YEAR = {
    "cardekho_IN": 2022,
    "uk_used_cars": 2020,
}

# At inference time in the live app, Vehicle_Age is instead computed as
# (real current year - manufacture_year) - see backend/app/services/ml_pipeline.py.
LIVE_REFERENCE_YEAR = 2026

UK_BRAND_FROM_FILENAME = {
    "audi": "Audi",
    "bmw": "BMW",
    "ford": "Ford",
    "hyundi": "Hyundai",
    "merc": "Mercedes-Benz",
    "skoda": "Skoda",
    "toyota": "Toyota",
    "vauxhall": "Opel",  # Vauxhall is GM's UK-market brand name for Opel
    "vw": "Volkswagen",
}

VALID_FUEL_TYPES = {"Petrol", "Diesel", "CNG", "LPG", "Electric", "Hybrid"}


def load_india_dataset() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "cardekho_v4.csv")
    df = df.rename(
        columns={
            "Make": "make",
            "Year": "year",
            "Fuel Type": "fuel_type",
            "Owner": "ownership",
            "Kilometer": "kilometers_driven",
        }
    )
    df = df[["make", "year", "fuel_type", "ownership", "kilometers_driven"]].copy()
    # Drop dirty combined fuel-type values ("Petrol + CNG", "CNG + CNG", ...) - a handful of rows.
    df = df[df["fuel_type"].isin(VALID_FUEL_TYPES)]
    df["source"] = "cardekho_IN"
    return df


def load_uk_dataset() -> pd.DataFrame:
    frames = []
    for filename, brand in UK_BRAND_FROM_FILENAME.items():
        path = RAW_DIR / "uk_cars" / f"{filename}.csv"
        raw = pd.read_csv(path)
        raw.columns = [c.strip() for c in raw.columns]
        raw = raw.rename(columns={"tax(£)": "tax"})
        raw["make"] = brand
        raw["ownership"] = "Unknown"  # not present in the UK source
        raw = raw.rename(columns={"year": "year", "fuelType": "fuel_type", "mileage": "kilometers_driven"})
        frames.append(raw[["make", "year", "fuel_type", "ownership", "kilometers_driven"]])
    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = df.drop_duplicates()
    print(f"  UK: dropped {before - len(df)} exact-duplicate rows")
    df = df[df["fuel_type"].isin(VALID_FUEL_TYPES)]
    df["source"] = "uk_used_cars"
    return df


def build_dataset() -> pd.DataFrame:
    india = load_india_dataset()
    uk = load_uk_dataset()
    print(f"India rows: {len(india)} | UK rows: {len(uk)}")

    df = pd.concat([india, uk], ignore_index=True)
    df["vehicle_age"] = df["source"].map(SOURCE_SNAPSHOT_YEAR) - df["year"]

    before = len(df)
    df = df.dropna(subset=["make", "vehicle_age", "fuel_type", "kilometers_driven"])
    df = df[(df["vehicle_age"] >= 0) & (df["vehicle_age"] <= 30)]
    df = df[(df["kilometers_driven"] > 0) & (df["kilometers_driven"] <= 500_000)]
    print(f"Combined rows: {before} -> {len(df)} after cleaning/outlier filtering")

    # Group rare makes into "Other" to keep the one-hot vocabulary small and generalizable.
    make_counts = df["make"].value_counts()
    common_makes = set(make_counts[make_counts >= 30].index)
    df["make"] = df["make"].where(df["make"].isin(common_makes), "Other")

    return df


def main() -> None:
    print("=== Loading & cleaning data ===")
    df = build_dataset()
    print(df[["make", "fuel_type", "ownership"]].describe(include="object"))
    print(f"\nFinal dataset: {len(df)} rows")
    print(f"Makes: {sorted(df['make'].unique())}")

    X = df[["make", "vehicle_age", "fuel_type", "ownership"]]
    y = df["kilometers_driven"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), ["make", "fuel_type", "ownership"]),
        ],
        remainder="passthrough",  # vehicle_age passes through as-is
    )

    print("\n=== Baseline: Linear Regression ===")
    baseline = Pipeline([("prep", preprocessor), ("model", LinearRegression())])
    baseline.fit(X_train, y_train)
    evaluate(baseline, X_test, y_test, "Linear Regression")

    print("\n=== Candidate: Random Forest Regressor ===")
    candidate = Pipeline(
        [
            ("prep", preprocessor),
            ("model", RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_leaf=5, random_state=42, n_jobs=-1)),
        ]
    )
    candidate.fit(X_train, y_train)
    evaluate(candidate, X_test, y_test, "Random Forest")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELS_DIR / "regression_mileage.joblib"
    joblib.dump(candidate, out_path)
    print(f"\nSaved {out_path}")

    print("\n=== Sanity check: real vehicle from our Gov API test (Hyundai Bayon, 2023, Petrol) ===")
    sample = pd.DataFrame(
        [{"make": "Hyundai", "vehicle_age": LIVE_REFERENCE_YEAR - 2023, "fuel_type": "Petrol", "ownership": "Unknown"}]
    )
    pred = candidate.predict(sample)[0]
    print(f"Predicted Kilometers_Driven: {pred:,.0f} km")

    print("\n=== Monotonicity check: predicted mileage across ages 1-15 (Hyundai, Petrol) ===")
    ages = pd.DataFrame(
        [{"make": "Hyundai", "vehicle_age": a, "fuel_type": "Petrol", "ownership": "Unknown"} for a in range(1, 16)]
    )
    for age, pred in zip(ages["vehicle_age"], candidate.predict(ages)):
        print(f"  age={age:>2} -> {pred:>8,.0f} km")


def evaluate(model, X_test, y_test, label: str) -> None:
    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"{label}: RMSE={rmse:,.0f} km | MAE={mae:,.0f} km | R2={r2:.3f}")


if __name__ == "__main__":
    main()
