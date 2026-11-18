import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ml.registry import get_models
from app.schemas.prediction import PredictionResponse
from app.services.prediction import build_prediction, get_recalls
from app.services.vehicle_lookup import get_vehicle_profile

router = APIRouter(prefix="/api/v1/predict", tags=["prediction"])

LICENSE_PLATE_PATTERN = r"^\d{7,8}$"


@router.get("/{license_plate}", response_model=PredictionResponse)
async def predict(
    license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN),
    odometer_km: int | None = Query(default=None, ge=0, le=1_500_000, description="Measured odometer reading (km), if known"),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    # the recall lookup only needs the plate: run it in parallel with the registry lookup
    recalls_task = asyncio.create_task(get_recalls(license_plate))
    profile = await get_vehicle_profile(license_plate)
    if profile is None:
        recalls_task.cancel()
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")
    return await build_prediction(profile, get_models(), session, odometer_km=odometer_km, recalls_info=await recalls_task)
