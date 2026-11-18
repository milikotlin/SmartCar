import asyncio
import json
from typing import Any

import httpx

from app.config import settings

CKAN_DATASTORE_SEARCH_URL = "https://data.gov.il/api/3/action/datastore_search"


class RegistryUnavailableError(Exception):
    """The Ministry of Transport service did not answer (timeout, network error or HTTP error)."""


async def fetch_vehicle_record(license_plate: str, attempts: int = 2) -> dict[str, Any] | None:
    params = {
        "resource_id": settings.gov_api_resource_id,
        "filters": json.dumps({"mispar_rechev": license_plate}),
        "limit": 1,
    }
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(CKAN_DATASTORE_SEARCH_URL, params=params)
                response.raise_for_status()
            records = response.json()["result"]["records"]
            return records[0] if records else None
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last = exc
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RegistryUnavailableError(f"registry unavailable ({type(last).__name__})")
