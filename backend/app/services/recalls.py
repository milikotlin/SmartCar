"""Official open recalls per plate (Ministry of Transport, data.gov.il dataset "vehicles with open recalls").

A recall is a manufacturer/authority FACT about a vehicle, not a prediction; it is shown separately from the ML risk and from maintenance rules.
"""
import json
from typing import Any

import httpx

from app.config import settings

CKAN_URL = "https://data.gov.il/api/3/action/datastore_search"

CATEGORY_EN = {
    "כריות אוויר": "Airbags", "מנוע ומערכותיו": "Engine and systems", "אחר": "Other", "היגוי ומתלים": "Steering and suspension",
    "מרכב ושילדה": "Body and chassis", "חשמל אליקטרוניקה ומיזוג": "Electrical, electronics and A/C", "בלמים": "Brakes",
    "מערכת הבטיחות": "Safety system", "מערכת הדלק": "Fuel system", "מערכת הפליטה": "Exhaust system", "חגורות בטיחות": "Seat belts",
    "מערכת העברת כוח": "Drivetrain", "מערכת יציבות": "Stability system", "אביזרים": "Accessories",
}
RECALL_TYPE_EN = {"תקלה סידרתית בטיחותית": "Serial safety defect", "קמפיין שרות טכני": "Technical service campaign"}
RELATED_SYSTEM = {"בלמים": "brakes", "חשמל אליקטרוניקה ומיזוג": "electrical", "מנוע ומערכותיו": "engine_emissions", "מערכת הדלק": "engine_emissions", "מערכת הפליטה": "engine_emissions"}


def translate_recall(r: dict[str, Any]) -> dict[str, Any]:
    category = r.get("SUG_TAKALA", "") or ""
    return {
        "recall_id": r.get("RECALL_ID"),
        "type": RECALL_TYPE_EN.get(r.get("SUG_RECALL", ""), r.get("SUG_RECALL")),
        "category": CATEGORY_EN.get(category, category),
        "related_system": RELATED_SYSTEM.get(category),
        "description_he": r.get("TEUR_TAKALA"),          # official text, kept in Hebrew as published
        "opened": r.get("TAARICH_PTICHA"),
    }


async def fetch_open_recalls(license_plate: str) -> list[dict[str, Any]]:
    params = {"resource_id": settings.gov_recalls_resource_id, "filters": json.dumps({"MISPAR_RECHEV": int(license_plate)}), "limit": 100}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(CKAN_URL, params=params)
        response.raise_for_status()
    return [translate_recall(r) for r in response.json()["result"]["records"]]
