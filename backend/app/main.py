from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.api.v1.predict import router as predict_router
from app.api.v1.records import router as records_router
from app.api.v1.vehicles import router as vehicles_router
from app.ml.registry import get_models


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_models()  # load both models once; fail fast if an artifact is missing
    yield


app = FastAPI(title="SmartCar-Ops API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles_router)
app.include_router(predict_router)
app.include_router(records_router)
app.include_router(chat_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
