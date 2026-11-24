import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.i18n import DEFAULT_LANG, Lang
from app.i18n.localize import localize_prediction
from app.ml.registry import get_models
from app.schemas.prediction import PredictionResponse
from app.services.prediction import build_prediction, get_recalls
from app.services.vehicle_lookup import get_vehicle_profile

router = APIRouter(prefix="/api/v1/predict", tags=["prediction"])

LICENSE_PLATE_PATTERN = r"^\d{7,8}$"


@router.get("/{license_plate}", response_model=PredictionResponse)
async def predict(
    license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN),
    odometer_km: int | None = Query(default=None, ge=1, le=1_000_000, description="Mileage typed by the user (km). Reported, NOT verified, never stored; used for this response only"),
    lang: Lang = Query(default=DEFAULT_LANG, description="Language of the texts (en | he). Numbers, levels and model inputs do not depend on it"),
    session: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    # the recall lookup only needs the plate: run it in parallel with the registry lookup
    recalls_task = asyncio.create_task(get_recalls(license_plate))
    profile = await get_vehicle_profile(license_plate)
    if profile is None:
        recalls_task.cancel()
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")
    prediction = await build_prediction(profile, get_models(), session, odometer_km=odometer_km, recalls_info=await recalls_task)
    return localize_prediction(prediction, lang)
