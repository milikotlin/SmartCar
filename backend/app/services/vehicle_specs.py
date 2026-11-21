"""Official data that the Model 1 of Smart_Car_Models.pdf needs and the vehicle registry record does not carry (data.gov.il, Ministry of Transport):

  * engine volume (nefah_manoa, cc) and automatic transmission (automatic_ind): the model table "תוצרים ודגמים של כלי רכב WLTP", looked up by manufacturer
    code + model code + year of the registry record;
  * number of owners (Dataset 8 `Owner_Type`): the ownership-history table of private vehicles, one row per ownership (the first one included: a car
    registered in 2026-11 has one row). Older cars outside the period the table covers have no row: their owner type is "Unknown", never guessed.

Both are cached 24 h in Redis like the registry. Any failure returns "unknown" (None): the KNN imputer of Model 1 then fills engine size / transmission
from similar vehicles, and the owner type is "Unknown"; the API says so in the mileage notes.
"""
import json
from dataclasses import dataclass

import httpx

from app.redis_client import get_cached, set_cached

URL = "https://data.gov.il/api/3/action/datastore_search"
WLTP_RESOURCE = "142afde2-6228-49f9-8a29-9b6c3a0cbe40"
OWNERSHIP_RESOURCE = "bb2355dc-9ec7-4f06-9c3f-3344672171da"


@dataclass
class VehicleSpecs:
    engine_cc: float | None = None
    automatic: float | None = None
    owner_changes: int | None = None          # ownership rows recorded for the plate (None = the lookup failed); kept name for the cache format
    source_note: str | None = None


async def _search(resource: str, filters: dict, limit: int = 50) -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(URL, params={"resource_id": resource, "filters": json.dumps(filters), "limit": limit})
            r.raise_for_status()
        return r.json()["result"]["records"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def get_vehicle_specs(plate: str, tozeret_cd, degem_cd, year: int) -> VehicleSpecs:
    key = f"specs:{plate}"
    cached = await get_cached(key)
    if cached is not None:
        return VehicleSpecs(**cached)
    specs = VehicleSpecs()
    notes = []
    if tozeret_cd is not None and degem_cd is not None:
        rows = await _search(WLTP_RESOURCE, {"tozeret_cd": int(tozeret_cd), "degem_cd": int(degem_cd), "shnat_yitzur": int(year)}, limit=5)
        if rows:
            cc = next((r.get("nefah_manoa") for r in rows if r.get("nefah_manoa")), None)
            auto = next((r.get("automatic_ind") for r in rows if r.get("automatic_ind") is not None), None)
            specs.engine_cc = float(cc) if cc else None
            specs.automatic = float(auto) if auto is not None else None
        elif rows is None:
            notes.append("official model table unavailable")
    owners = await _search(OWNERSHIP_RESOURCE, {"mispar_rechev": int(plate)}, limit=50)
    specs.owner_changes = len(owners) if owners is not None else None
    specs.source_note = "; ".join(notes) or None
    complete = owners is not None and "official model table unavailable" not in notes
    if complete:
        await set_cached(key, specs.__dict__)
    return specs


def owner_count(specs: VehicleSpecs) -> int | None:
    """Ownership rows recorded -> number of owners. No row (car older than the table) or a failed lookup -> unknown."""
    return specs.owner_changes if specs.owner_changes else None
