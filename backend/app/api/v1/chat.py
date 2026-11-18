from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ml.registry import get_models
from app.services import chat
from app.services.prediction import build_prediction
from app.services.vehicle_lookup import get_vehicle_profile

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    license_plate: str = Field(pattern=r"^\d{7,8}$")
    message: str = Field(min_length=1, max_length=1000)
    odometer_km: int | None = Field(default=None, ge=0, le=1_500_000)


class ChatResponse(BaseModel):
    answer: str
    source: str  # openai | deterministic_fallback
    model: str | None = None
    note: str | None = None
    context: list[str]  # the facts injected into the prompt (transparency)


@router.post("", response_model=ChatResponse)
async def diagnostic_chat(body: ChatRequest, session: AsyncSession = Depends(get_db)) -> ChatResponse:
    profile = await get_vehicle_profile(body.license_plate)
    if profile is None:
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")
    prediction = await build_prediction(profile, get_models(), session, odometer_km=body.odometer_km)
    result = await chat.answer(prediction, body.message)
    return ChatResponse(
        answer=result["answer"],
        source=result["source"],
        model=result.get("model"),
        note=result.get("note"),
        context=chat.facts(prediction, date.today()),
    )
