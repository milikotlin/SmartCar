"""Turns a translated registry profile into the canonical inputs of Model 1 and Model 2 (only fields that exist for any Israeli plate)."""
from datetime import date, datetime

from app.config import settings
from app.ml.risk import RiskInputs
from app.schemas.vehicle import VehicleProfile

FUEL_KEY = {"Petrol": "petrol", "Diesel": "diesel", "Hybrid": "hybrid", "Plug-in Hybrid": "hybrid", "Electric": "electric", "LPG/CNG": "lpg_cng", "LPG": "lpg_cng"}
OWNERSHIP_KEY = {"Private": "private", "Dealer": "private", "Leasing": "leasing", "Company": "company", "Rental": "rental"}
MAKE_ALIAS = {"Vauxhall": "Opel"}


def current_year() -> int:
    return settings.reference_year or date.today().year


def fuel_key(profile: VehicleProfile) -> str:
    return FUEL_KEY.get(profile.fuel_type, "unknown")


def ownership_key(profile: VehicleProfile) -> str | None:
    return OWNERSHIP_KEY.get(profile.ownership)


def vehicle_age(profile: VehicleProfile) -> int:
    return max(current_year() - profile.manufacture_year, 0)


def model_make(profile: VehicleProfile) -> str:
    """Spelling used in the training data: title case (BMW -> Bmw), Vauxhall/Opel unified."""
    make = (profile.make or "").strip().title()
    return MAKE_ALIAS.get(make, make)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def first_use_year(profile: VehicleProfile) -> int:
    """Registry first-registration month ("2019-2") when present, else the manufacture year."""
    if profile.first_registration:
        try:
            return int(profile.first_registration.split("-")[0])
        except ValueError:
            pass
    return profile.manufacture_year


def last_test_date(profile: VehicleProfile, inspection_date: date | None = None) -> date | None:
    return inspection_date or _parse_date(profile.last_test_date)


def planned_gap_years(profile: VehicleProfile, last_test: date | None) -> float:
    """Interval to the next annual test from the registry (license valid until - last test); 1.0 when unavailable or implausible."""
    valid = _parse_date(profile.license_valid_until)
    if valid and last_test:
        gap = (valid - last_test).days / 365.25
        if 0.5 <= gap <= 1.7:
            return round(gap, 3)
    return 1.0


def risk_inputs(profile: VehicleProfile, previous: dict | None, odometer_km: float | None, inspection_date: date | None = None) -> RiskInputs:
    test_date = last_test_date(profile, inspection_date)
    year_of_test = test_date.year if test_date else current_year()
    return RiskInputs(
        age_year=year_of_test - first_use_year(profile),
        gap_next=planned_gap_years(profile, test_date),
        fuel=fuel_key(profile),
        make=model_make(profile),
        previous=previous,
        odometer_km=odometer_km,
    )
