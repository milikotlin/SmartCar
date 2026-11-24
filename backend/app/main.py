from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.api.v1.garages import router as garages_router
from app.api.v1.predict import router as predict_router
from app.api.v1.records import router as records_router
from app.api.v1.vehicles import router as vehicles_router
from app.config import settings
from app.ml.registry import get_models
from app.services.gov_api import RegistryUnavailableError


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_models()  # load both models once; fail fast if an artifact is missing
    yield


app = FastAPI(title="SmartCar-Ops API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],     # only the dashboard (was "*")
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Write-Key"],
)

@app.exception_handler(RegistryUnavailableError)
async def registry_unavailable_handler(_: Request, exc: RegistryUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": f"The Ministry of Transport registry is temporarily unavailable ({exc}). Please try again in a moment."})


app.include_router(vehicles_router)
app.include_router(predict_router)
app.include_router(records_router)
app.include_router(chat_router)
app.include_router(garages_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
