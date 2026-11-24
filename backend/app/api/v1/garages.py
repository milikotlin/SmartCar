from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.i18n import DEFAULT_LANG, Lang
from app.security import rate_limit
from app.services import garages, google_places

router = APIRouter(prefix="/api/v1/garages", tags=["garages"], dependencies=[Depends(rate_limit("garages", lambda: settings.garages_rate_per_minute))])

Service = Literal["mechanics", "ev_hybrid", "electrical", "brakes", "tires", "suspension", "air_conditioning", "bodywork", "gearbox", "exhaust_cooling", "pre_purchase"]


class City(BaseModel):
    code: int
    name_he: str
    name_en: str
    garages: int


class Garage(BaseModel):
    id: int                                # licence number of the garage in the official register
    name: str                              # as published (Hebrew)
    address: str
    locality: str
    city_he: str
    city_en: str
    phone: str
    services: list[str]
    lat: float | None
    lon: float | None
    position: str                          # house (house number mapped) | street (the street is mapped) | none (not on the map)
    distance_km: float | None              # straight line; None when the position is not known
    in_city: bool | None
    opening_hours: str | None              # OpenStreetMap, when the business states them there
    google_maps_url: str
    waze_url: str
    google_search_url: str


class Centre(BaseModel):
    lat: float
    lon: float


class GarageResults(BaseModel):
    mode: Literal["city", "gps"]
    city: City | None = None
    centre: Centre | None = None           # of the city (never the user's own position)
    approximate: bool                      # True for a city search: distances are from the centre of the city
    radius_km: float
    total: int
    total_in_city: int | None = None
    without_position: int
    offset: int
    items: list[Garage]
    ratings_available: bool                # a Google key is configured: ratings can be requested garage by garage
    source: str = "data.gov.il: Ministry of Transport and Road Safety, licensed garages"
    as_of: str
    stale: bool


class NearRequest(BaseModel):
    """The position travels in the body (not in the URL), is used in memory only and is never stored."""

    lat: float = Field(ge=29.0, le=33.6)
    lon: float = Field(ge=34.0, le=36.0)
    radius_km: float = Field(default=10, ge=1, le=50)
    service: Service | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GoogleDetails(BaseModel):
    matched: bool
    name: str | None = None
    address: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    phone: str | None = None
    opening_hours: list[str] = []
    url: str | None = None
    attribution: str | None = None


async def _register() -> dict:
    try:
        return await garages.register()
    except garages.GarageRegisterUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"The official garage register is temporarily unavailable ({exc}). Please try again in a moment.") from exc


def _results(reg: dict, found: list[dict], limit: int, offset: int, **kw) -> GarageResults:
    return GarageResults(total=len(found), without_position=sum(g["position"] == "none" for g in found), offset=offset, items=[Garage(**g) for g in found[offset : offset + limit]],
                         ratings_available=google_places.enabled(), as_of=reg["as_of"], stale=reg["stale"], **kw)


@router.get("/cities", response_model=list[City])
async def cities(q: str = Query(default="", max_length=60), limit: int = Query(default=8, ge=1, le=20)) -> list[City]:
    """Official localities by Hebrew or English name; without a text, the localities with most garages."""
    reg = await _register()
    return [City(**c) for c in garages.search_cities(q, garages.city_counts(reg["garages"]), limit)]


@router.get("", response_model=GarageResults)
async def by_city(city: int = Query(description="official locality code (from /cities)"), radius_km: float = Query(default=10, ge=1, le=50), service: Service | None = Query(default=None),
                  limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> GarageResults:
    place = garages.geo()["localities"].get(city)
    if place is None:
        raise HTTPException(status_code=404, detail="Unknown locality code")
    reg = await _register()
    found = garages.find(reg["garages"], place["lat"], place["lon"], radius_km, service, city)
    here = sum(bool(g["in_city"]) for g in found)
    return _results(reg, found, limit, offset, mode="city", city=City(code=city, name_he=place["he"], name_en=place["en"], garages=here), centre=Centre(lat=place["lat"], lon=place["lon"]),
                    approximate=True, radius_km=radius_km, total_in_city=here)


@router.post("/near", response_model=GarageResults)
async def near(body: NearRequest) -> GarageResults:
    """Garages around the user's own position (given with the user's permission), nearest first."""
    reg = await _register()
    found = garages.find(reg["garages"], body.lat, body.lon, body.radius_km, body.service)
    return _results(reg, found, body.limit, body.offset, mode="gps", approximate=False, radius_km=body.radius_km)


@router.get("/{garage_id}/google", response_model=GoogleDetails)
async def google_details(garage_id: int = Path(ge=1), lang: Lang = Query(default=DEFAULT_LANG)) -> GoogleDetails:
    if not google_places.enabled():
        raise HTTPException(status_code=404, detail="Ratings are not configured on this server")
    reg = await _register()
    raw = next((g for g in reg["garages"] if g["id"] == garage_id), None)
    if raw is None:
        raise HTTPException(status_code=404, detail="Unknown garage")
    try:
        place = await google_places.details(garages._present(raw, None, None), lang)
    except google_places.PlacesQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail="The daily limit of rating look-ups has been reached") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:          # the key or Google's answer never reaches the client
        raise HTTPException(status_code=503, detail=f"Ratings are temporarily unavailable ({type(exc).__name__})") from exc
    return GoogleDetails(matched=place is not None, **(place or {}))
