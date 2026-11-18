from app.redis_client import get_cached, set_cached
from app.schemas.vehicle import VehicleProfile
from app.services import gov_api, translation


async def get_vehicle_profile(license_plate: str) -> VehicleProfile | None:
    """Registry profile with the 24 h Redis cache (NFR-1). Returns None when the plate is not in the registry."""
    cache_key = f"vehicle:{license_plate}"
    cached = await get_cached(cache_key)
    if cached is not None:
        return VehicleProfile.model_validate(cached)
    record = await gov_api.fetch_vehicle_record(license_plate)
    if record is None:
        return None
    profile = translation.translate_vehicle_record(record)
    await set_cached(cache_key, profile.model_dump())
    return profile
