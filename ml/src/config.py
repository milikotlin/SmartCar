"""Shared paths for the Sprint 3 ML experiments.

Raw datasets live OUTSIDE the project (default: ~/smartcar_data) because they are
large (Craigslist alone is ~1.4 GB) and the project folder is synced by OneDrive.
Override with the SMARTCAR_DATA_DIR environment variable.
"""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("SMARTCAR_DATA_DIR", Path.home() / "smartcar_data"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"

# Dataset numbers follow SmartCar_Data.pdf / Smart_Car_Models.pdf.
KAGGLE_DATASETS = {
    "d1_logistics": "datasetengineer/logistics-vehicle-maintenance-history-dataset",
    "d3_cardekho": "manishkr1754/cardekho-used-car-data",
    "d4_telemetry": "tejalaveti2306/vehicle-maintenance-telemetry-data",
    "d5_nev_faults": "ziya07/fault-prediction-and-optimization-in-nevs",
    "d6_craigslist": "austinreese/craigslist-carstrucks-data",
    "d7_uk_cars": "adityadesai13/used-car-dataset-ford-and-mercedes",
    "d8_used_cars_in": "avikasliwal/used-cars-price-prediction",
}

MILES_TO_KM = 1.609344
