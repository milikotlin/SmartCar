import json
from typing import Any

import httpx

from app.config import settings

CKAN_DATASTORE_SEARCH_URL = "https://data.gov.il/api/3/action/datastore_search"


async def fetch_vehicle_record(license_plate: str) -> dict[str, Any] | None:
    params = {
        "resource_id": settings.gov_api_resource_id,
        "filters": json.dumps({"mispar_rechev": license_plate}),
        "limit": 1,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(CKAN_DATASTORE_SEARCH_URL, params=params)
        response.raise_for_status()

    records = response.json()["result"]["records"]
    return records[0] if records else None
