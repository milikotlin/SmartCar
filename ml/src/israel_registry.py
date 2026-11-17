"""Normalisation of the Israeli registry sample (Hebrew) to the canonical English
vocabulary shared by all training datasets. Used ONLY for Sprint 3 research
(coverage / market-compatibility analysis); the production translation lives in
backend/app/services/translation.py and is intentionally left untouched.
"""
import re

import pandas as pd

# Hebrew manufacturer prefix -> canonical make. tozeret_nm = "<brand> <country>", and the
# registry truncates it to ~14 chars, so we match on the brand prefix (longest first).
HE_MAKE_PREFIX = {
    "מרוטי סוזוקי": "Suzuki", "קיה": "Kia", "יונדאי": "Hyundai", "טויוטה": "Toyota",
    "סקודה": "Skoda", "מזדה": "Mazda", "סוזוקי": "Suzuki", "מיצובישי": "Mitsubishi",
    "ניסאן": "Nissan", "רנו": "Renault", "ג'ילי": "Geely", "צ'רי": "Chery", "סיאט": "Seat",
    "ג'אקו": "Jaecoo", "פולקסווגן": "Volkswagen", "שברולט": "Chevrolet", "הונדה": "Honda",
    "פיג'ו": "Peugeot", "סובארו": "Subaru", "סיטרואן": "Citroen", "מ.ג'י": "MG",
    "דאצ'יה": "Dacia", "דאציה": "Dacia", "מרצדס": "Mercedes-Benz", "דייהטסו": "Daihatsu",
    "טסלה": "Tesla", "אקספנג": "Xpeng", "איסוזו": "Isuzu", "ב מ וו": "BMW", "בי.מ.וו": "BMW",
    "לקסוס": "Lexus", "בי ווי די": "BYD", "אופל": "Opel", "פורד": "Ford", "וולבו": "Volvo",
    "אאודי": "Audi", "דיפאל": "Deepal", "אומודה": "Omoda", "קרייזלר": "Chrysler", "ג'יפ": "Jeep",
    "פיאט": "Fiat", "מיני": "Mini", "לנד רובר": "Land Rover", "פורשה": "Porsche",
    "אלפא רומיאו": "Alfa Romeo", "קופרה": "Cupra", "ג'נסיס": "Genesis", "סמארט": "Smart",
}
_PREFIXES = sorted(HE_MAKE_PREFIX, key=len, reverse=True)

HE_FUEL = {
    "בנזין": "petrol",
    "דיזל": "diesel",
    "חשמל": "electric",
    "חשמל/בנזין": "hybrid",
    "חשמל/דיזל": "hybrid",
    'גפמ"': "lpg_cng",
}

HE_OWNERSHIP = {
    "פרטי": "private", "ליסינג": "leasing", "חברה": "company", "סוחר": "dealer", "השכרה": "rental",
}


def he_make(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name).replace('"', "").strip())
    for prefix in _PREFIXES:
        if s.startswith(prefix):
            return HE_MAKE_PREFIX[prefix]
    return "Unmapped"


def normalise_registry(df: pd.DataFrame, reference_year: int = 2026, passenger_only: bool = True) -> pd.DataFrame:
    d = df.copy()
    if passenger_only:
        d = d[d["sug_degem"] == "P"]
    out = pd.DataFrame(
        {
            "make": d["tozeret_nm"].map(he_make),
            "age": reference_year - d["shnat_yitzur"],
            "fuel": d["sug_delek_nm"].map(HE_FUEL),
            "ownership": d["baalut"].map(HE_OWNERSHIP),
            "model_raw": d["kinuy_mishari"],
        }
    )
    return out.reset_index(drop=True)
