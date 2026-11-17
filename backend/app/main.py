from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.vehicles import router as vehicles_router

app = FastAPI(title="SmartCar-Ops API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
