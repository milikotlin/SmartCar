"""
Brand_Reliability_Index (0-100): a hand-curated lookup table, NOT learned from
the Kaggle datasets - none of the three source datasets label reliability or
failure rate by manufacturer (the maintenance dataset only has a coarse
vehicle *type*: Car/SUV/Van/Truck/Bus/Motorcycle, not a brand).

Scores are a rough, defensible approximation based on widely publicized
reliability-survey tiers (e.g. Consumer Reports / J.D. Power style rankings
of long-run dependability), not a precise or original measurement. Unlisted
makes fall back to DEFAULT_SCORE (a neutral "unknown brand" assumption).

This is intentionally simple: at training time (see train_classification.py)
this feature is injected as an UNINFORMATIVE random value, since we have no
ground truth linking Kaggle rows to a real brand's failure rate. It's included
in the model's feature vector to match the SRS-specified feature set (Age,
Mileage, Days_Since_Last, Brand_Reliability), and the model's feature
importance analysis documents that it currently contributes ~0 - a known
limitation until a brand-labeled reliability dataset is available.
"""

DEFAULT_SCORE = 60

BRAND_RELIABILITY_INDEX: dict[str, int] = {
    "Toyota": 90,
    "Lexus": 90,
    "Honda": 87,
    "Mazda": 85,
    "Suzuki": 84,
    "Hyundai": 80,
    "Kia": 79,
    "Skoda": 78,
    "Subaru": 78,
    "Volkswagen": 74,
    "Nissan": 74,
    "Mercedes-Benz": 70,
    "BMW": 68,
    "Audi": 67,
    "Ford": 66,
    "Volvo": 72,
    "Peugeot": 62,
    "Citroen": 60,
    "Opel": 60,
    "Fiat": 55,
    "Renault": 58,
    "Mitsubishi": 76,
    "Mini": 60,
    "Jeep": 55,
    "Alfa Romeo": 50,
    "Daihatsu": 78,
}


def get_reliability(make: str) -> int:
    return BRAND_RELIABILITY_INDEX.get(make, DEFAULT_SCORE)
