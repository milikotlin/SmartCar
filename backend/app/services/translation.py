from typing import Any

from app.schemas.vehicle import VehicleProfile

FUEL_TYPE_TRANSLATIONS: dict[str, str] = {
    "בנזין": "Petrol",
    "דיזל": "Diesel",
    "חשמלי": "Electric",
    "היברידי": "Hybrid",
    "היברידי נטענת": "Plug-in Hybrid",
    "גז": "LPG",
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

# tozeret_nm often carries a country suffix (e.g. "יונדאי טורקיה" = "Hyundai Turkey"),
# so manufacturers are matched by prefix rather than exact match.
MANUFACTURER_TRANSLATIONS: dict[str, str] = {
    "יונדאי": "Hyundai",
    "טויוטה": "Toyota",
    "קיה": "Kia",
    "מאזדה": "Mazda",
    "סקודה": "Skoda",
    "פולקסווגן": "Volkswagen",
    "שברולט": "Chevrolet",
    "פורד": "Ford",
    "רנו": "Renault",
    "סוזוקי": "Suzuki",
    "מיצובישי": "Mitsubishi",
    "ניסאן": "Nissan",
    "הונדה": "Honda",
    "פיג'ו": "Peugeot",
    "סיטרואן": "Citroen",
    "אאודי": "Audi",
    "ב.מ.וו": "BMW",
    "מרצדס": "Mercedes-Benz",
    "וולוו": "Volvo",
    "סובארו": "Subaru",
    "אופל": "Opel",
    "סיאט": "Seat",
    "פיאט": "Fiat",
    "לקסוס": "Lexus",
    "דייהטסו": "Daihatsu",
    "אלפא רומיאו": "Alfa Romeo",
    "מיני": "Mini",
    "ג'יפ": "Jeep",
}


def _translate_manufacturer(raw: str) -> str:
    for hebrew, english in MANUFACTURER_TRANSLATIONS.items():
        if raw.startswith(hebrew):
            return english
    return raw.strip()


def translate_vehicle_record(record: dict[str, Any]) -> VehicleProfile:
    fuel_raw = record.get("sug_delek_nm", "")
    ownership_raw = record.get("baalut", "")

    return VehicleProfile(
        license_plate=str(record["mispar_rechev"]),
        make=_translate_manufacturer(record.get("tozeret_nm", "")),
        model=record.get("kinuy_mishari") or record.get("degem_nm", ""),
        manufacture_year=int(record["shnat_yitzur"]),
        fuel_type=FUEL_TYPE_TRANSLATIONS.get(fuel_raw, fuel_raw),
        ownership=OWNERSHIP_TRANSLATIONS.get(ownership_raw, ownership_raw),
        color=record.get("tzeva_rechev"),
        last_test_date=record.get("mivchan_acharon_dt"),
    )
