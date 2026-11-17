from fastapi import APIRouter, HTTPException, Path

from app.redis_client import get_cached, set_cached
from app.schemas.vehicle import VehicleProfile
from app.services import gov_api, translation

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

LICENSE_PLATE_PATTERN = r"^\d{7,8}$"


@router.get("/{license_plate}", response_model=VehicleProfile)
async def get_vehicle_profile(
    license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN),
) -> VehicleProfile:
    cache_key = f"vehicle:{license_plate}"

    cached = await get_cached(cache_key)
    if cached is not None:
        return VehicleProfile.model_validate(cached)

    record = await gov_api.fetch_vehicle_record(license_plate)
    if record is None:
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")

    profile = translation.translate_vehicle_record(record)
    await set_cached(cache_key, profile.model_dump())
    return profile
