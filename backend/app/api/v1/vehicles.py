from fastapi import APIRouter, HTTPException, Path

from app.schemas.vehicle import VehicleProfile
from app.services.vehicle_lookup import get_vehicle_profile

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

LICENSE_PLATE_PATTERN = r"^\d{7,8}$"


@router.get("/{license_plate}", response_model=VehicleProfile)
async def get_vehicle_profile_route(
    license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN),
) -> VehicleProfile:
    profile = await get_vehicle_profile(license_plate)
    if profile is None:
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")
    return profile
