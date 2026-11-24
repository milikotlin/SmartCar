"""OPTIONAL rating, phone and opening hours of one garage (Google Places API, New). Off without GOOGLE_PLACES_API_KEY; the key stays in the backend.

Cost control: called only when the user opens the details of one garage, at most `google_places_daily_limit` times a day (counted in Redis; if the counter cannot be read, no call is made).
Google's terms: the content is never cached or stored and is shown with its attribution, without the OpenStreetMap map next to it. A result is accepted only when it is clearly the same business.
"""
import difflib
import re
from datetime import date

import httpx

from app.config import settings
from app.redis_client import _redis
from app.services.garages import distance_km

URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.regularOpeningHours.weekdayDescriptions,places.nationalPhoneNumber,places.googleMapsUri"


class PlacesQuotaExceeded(Exception):
    pass


def enabled() -> bool:
    return bool(settings.google_places_api_key)


async def _within_daily_limit() -> bool:
    key = f"google_places:{date.today().isoformat()}"
    try:
        n = await _redis.incr(key)
        if n == 1:
            await _redis.expire(key, 2 * 86400)
        return n <= settings.google_places_daily_limit
    except Exception:  # noqa: BLE001 - each call can cost money: without the counter no call is made
        return False


def _digits(s: str | None) -> str:
    d = re.sub(r"\D", "", s or "")
    return "0" + d[3:] if d.startswith("972") else d


def _name(s: str) -> str:
    return " ".join(re.sub(r"[^א-תa-z0-9 ]", " ", re.sub(r"בע\s?\"?מ|מוסך|ltd|garage", " ", s.lower())).split())


def same_business(garage: dict, place: dict) -> bool:
    """The same phone number, or a similar name at (almost) the same known position."""
    phone = _digits(garage["phone"])
    if phone and phone == _digits(place.get("nationalPhoneNumber")):
        return True
    loc = place.get("location") or {}
    if garage["position"] == "none" or "latitude" not in loc:
        return False
    near = distance_km(garage["lat"], garage["lon"], loc["latitude"], loc["longitude"]) <= (0.15 if garage["position"] == "house" else 0.4)
    return near and difflib.SequenceMatcher(None, _name(garage["name"]), _name((place.get("displayName") or {}).get("text", ""))).ratio() >= 0.6


async def details(garage: dict, lang: str, transport: httpx.AsyncBaseTransport | None = None) -> dict | None:
    """The Google entry of the garage, or None when Google has no entry that is clearly the same business."""
    if not await _within_daily_limit():
        raise PlacesQuotaExceeded()
    body = {"textQuery": " ".join(x for x in (garage["name"], garage["address"], garage["city_he"]) if x), "languageCode": lang, "regionCode": "IL", "pageSize": 3}
    if garage["position"] != "none":
        body["locationBias"] = {"circle": {"center": {"latitude": garage["lat"], "longitude": garage["lon"]}, "radius": 1500.0}}
    headers = {"X-Goog-Api-Key": settings.google_places_api_key, "X-Goog-FieldMask": FIELDS}
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
        r = await client.post(URL, json=body, headers=headers)
        r.raise_for_status()
    place = next((p for p in r.json().get("places", []) if same_business(garage, p)), None)
    if place is None:
        return None
    return {"name": (place.get("displayName") or {}).get("text"), "address": place.get("formattedAddress"), "rating": place.get("rating"), "rating_count": place.get("userRatingCount"),
            "phone": place.get("nationalPhoneNumber"), "opening_hours": (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or [], "url": place.get("googleMapsUri"), "attribution": "Google Maps"}
