"""Hebrew -> English translation of the Ministry of Transport registry record (FR-2).

The vocabularies below were checked against a random sample of 20,000 real registry rows (values of `sug_delek_nm`, `baalut`
and the manufacturer prefixes of `tozeret_nm`); an unknown value is returned as published instead of being guessed.
"""
import re
from typing import Any

from app.schemas.vehicle import VehicleProfile

# Exact values of `sug_delek_nm` found in the registry (+ the spellings used by the first implementation).
FUEL_TYPE_TRANSLATIONS: dict[str, str] = {
    "בנזין": "Petrol",
    "דיזל": "Diesel",
    "חשמל": "Electric",
    "חשמלי": "Electric",
    "חשמל/בנזין": "Hybrid",
    "חשמל/דיזל": "Hybrid",
    "היברידי": "Hybrid",
    "היברידי נטענת": "Plug-in Hybrid",
    'גפמ"': "LPG/CNG",
    "גז": "LPG/CNG",
}

OWNERSHIP_TRANSLATIONS: dict[str, str] = {
    "פרטי": "Private",
    "חברה": "Company",
    "ליסינג": "Leasing",
    "ממשלתי": "Government",
    "השכרה": "Rental",
    "ציבורי": "Public",
    "אגודה שיתופית": "Cooperative",
    "סוחר": "Dealer",
}

# `tozeret_nm` is "<brand> <country>" and is truncated by the registry, so manufacturers are matched by prefix (longest first).
MANUFACTURER_TRANSLATIONS: dict[str, str] = {
    "מרוטי סוזוקי": "Suzuki", "מרוטי": "Suzuki", "סוזוקי": "Suzuki",
    "יונדאי": "Hyundai", "טויוטה": "Toyota", "קיה": "Kia", "מזדה": "Mazda", "מאזדה": "Mazda", "סקודה": "Skoda",
    "פולקסווגן": "Volkswagen", "שברולט": "Chevrolet", "פורד": "Ford", "רנו": "Renault", "מיצובישי": "Mitsubishi",
    "ניסאן": "Nissan", "הונדה": "Honda", "פיג'ו": "Peugeot", "סיטרואן": "Citroen", "אאודי": "Audi",
    "ב.מ.וו": "BMW", "ב מ וו": "BMW", "בי.מ.וו": "BMW", "מרצדס": "Mercedes-Benz", "וולוו": "Volvo", "וולבו": "Volvo",
    "סובארו": "Subaru", "אופל": "Opel", "סיאט": "Seat", "פיאט": "Fiat", "לקסוס": "Lexus", "דייהטסו": "Daihatsu",
    "אלפא רומיאו": "Alfa Romeo", "אלפא": "Alfa Romeo", "מיני": "Mini", "ג'יפ": "Jeep", "ג'ילי": "Geely", "צ'רי": "Chery",
    "ג'אקו": "Jaecoo", "דאצ'יה": "Dacia", "דאציה": "Dacia", "טסלה": "Tesla", "אקספנג": "Xpeng", "איסוזו": "Isuzu",
    "בי ווי די": "BYD", "דיפאל": "Deepal", "אומודה": "Omoda", "קרייזלר": "Chrysler", 'מ.ג\'י': "MG", "מ.ג'י": "MG",
    "קופרה": "Cupra", "ג'נסיס": "Genesis", "סמארט": "Smart", "לנד רובר": "Land Rover", "לנדרובר": "Land Rover", "רובר": "Land Rover",
    "פורשה": "Porsche", "יגואר": "Jaguar", "ביואיק": "Buick", "קאדילאק": "Cadillac", "סאנגיונג": "SsangYong", "מקסוס": "Maxus",
    "אורה": "Ora", "לינק אנד קו": "Lynk & Co", "ליפמוטור": "Leapmotor", "זיקר": "Zeekr", "סרס": "Seres", "סקיוול": "Skywell",
    "דונגפנג": "Dongfeng", "אוואטר": "Avatr", "אף איי דבליו": "FAW", "איון": "Aion", "קיי ג'י מובילי": "KGM",
}
_PREFIXES = sorted(MANUFACTURER_TRANSLATIONS, key=len, reverse=True)


def translate_manufacturer(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").replace('"', "").strip())
    for hebrew in _PREFIXES:
        if s.startswith(hebrew):
            return MANUFACTURER_TRANSLATIONS[hebrew]
    return s


def translate_fuel(raw: str) -> str:
    return FUEL_TYPE_TRANSLATIONS.get(raw, raw)


def translate_ownership(raw: str) -> str:
    return OWNERSHIP_TRANSLATIONS.get(raw, raw)


def parse_cc(value: Any) -> int | None:
    """"1600 CC" -> 1600 (SRS data-pipeline test); returns None when there is no number."""
    m = re.search(r"\d[\d,]*", str(value)) if value is not None else None
    return int(m.group().replace(",", "")) if m else None


def translate_vehicle_record(record: dict[str, Any]) -> VehicleProfile:
    make_raw = record.get("tozeret_nm", "") or ""
    return VehicleProfile(
        license_plate=str(record["mispar_rechev"]),
        make=translate_manufacturer(make_raw),
        model=str(record.get("kinuy_mishari") or record.get("degem_nm") or "").strip(),
        manufacture_year=int(record["shnat_yitzur"]),
        fuel_type=translate_fuel(record.get("sug_delek_nm", "")),
        ownership=translate_ownership(record.get("baalut", "")),
        color=record.get("tzeva_rechev"),
        last_test_date=record.get("mivchan_acharon_dt"),
        license_valid_until=record.get("tokef_dt"),
        first_registration=record.get("moed_aliya_lakvish"),
        trim_level=record.get("ramat_gimur"),
        make_raw=make_raw,
    )
