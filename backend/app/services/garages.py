"""Licensed garages near a city or near the user (official register of the Ministry of Transport, data.gov.il, updated daily, no key).

* The register (name, address, locality, phone, licensed trades) is read whole, cached 24 h in Redis, and a copy is kept 30 days so that a data.gov.il outage does not empty the section.
* Positions and city names come from app/data/garage_geo.json (scripts/build_garage_geo.py). A position is used only while the register still publishes the same address.
* A garage without a known position is listed without a distance and is not drawn on the map. Nothing is guessed: no rating, no opening hours unless a source states them.
* The user's GPS position is used in memory to sort the answer: it is not cached, stored or sent to anyone.
"""
import asyncio
import difflib
import json
import math
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import settings
from app.redis_client import get_cached, set_cached

URL = "https://data.gov.il/api/3/action/datastore_search"
GEO_FILE = Path(__file__).resolve().parents[1] / "data" / "garage_geo.json"
CACHE_KEY, STALE_KEY, STALE_TTL = "garages:register:v1", "garages:register:stale:v1", 30 * 86400
MEMORY_SECONDS = 300
PAGE = 5000

# Licensed trades of the register that concern a private car -> service groups of the filter. Trades that are not here (trucks only, forklifts, tractors, licensing desks) are not shown.
SERVICE_OF_TRADE = {
    "מכונאות רכב בנזין": "mechanics", "מכונאות רכב דיזל": "mechanics", "אוטוטק רכב קל": "mechanics", "מכונאות רכב גפ מ": "mechanics", "חידוש ושיפוץ מנועים": "mechanics",
    "תיקון קרבורטורים": "mechanics", "תיקון משאבות ומתזים לדיזל": "mechanics",
    "תיקון אחזקת רכב חשמלי/היברידי": "ev_hybrid",
    "חשמלאות רכב": "electrical", "חידוש ושיפוץ מכללי חשמל": "electrical", "תיקון מחוונים": "electrical",
    "רפידות ותופי בלם": "brakes", "שיפוץ מכללי בלמים": "brakes",
    "תיקון והחלפת צמיגים": "tires", "אוטוטק תיקון והחלפת צמיגים": "tires",
    "תיקון וכוון מתלים ברכב": "suspension", "תיקון קפיצים ברכב מנועי": "suspension",
    "שירות תיקון למזגן אויר לרכב": "air_conditioning",
    "תיקון מרכבי רכב": "bodywork", "צבעות רכב": "bodywork", "אוטוטק מרכבי רכב וצביעתם": "bodywork", "אוטוטק מרכבי רכב וצביעתם +מסגרות": "bodywork",
    "תיקון תיבות הילוכים אוטומטיות": "gearbox",
    "תיקון צנורות פליטה ודודי עמם": "exhaust_cooling", "תיקון רדיאטורים )מצננים)": "exhaust_cooling",
    "בדיקות-רכב )קניה ומכירה)": "pre_purchase",
}
SERVICES = ["mechanics", "ev_hybrid", "electrical", "brakes", "tires", "suspension", "air_conditioning", "bodywork", "gearbox", "exhaust_cooling", "pre_purchase"]


class GarageRegisterUnavailable(Exception):
    """data.gov.il did not answer and no earlier copy of the register is stored."""


# ---------------------------------------------------------------- geometry and names (static file)
@lru_cache(maxsize=1)
def geo() -> dict:
    d = json.loads(GEO_FILE.read_text(encoding="utf-8"))
    d["localities"] = {int(k): v for k, v in d["localities"].items()}
    d["garages"] = {int(k): v for k, v in d["garages"].items()}
    return d


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle ("straight line") distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def _key_he(s: str) -> str:
    s = re.sub(r"[\"'׳״`’.*]", "", s)
    s = re.sub(r"יי+", "י", re.sub(r"וו+", "ו", re.sub(r"[-־–(),]", " ", s)))
    return " ".join(s.split())


def _key_en(s: str) -> str:
    """Transliteration-tolerant key: "Herzliya" = "HERZLIYYA", "Petah Tikva" = "PETAH TIQWA", "Kfar Saba" = "KEFAR SAVA"."""
    s = re.sub(r"[^a-z ]", "", s.lower().replace("-", " "))
    s = re.sub(r"\bkfar\b", "kefar", re.sub(r"\bbnei\b", "bene", re.sub(r"\bbeit\b", "bet", s)))
    for a, b in (("q", "k"), ("tz", "z"), ("ts", "z"), ("kh", "h"), ("ch", "h"), ("w", "v"), ("b", "v"), ("ph", "f"), ("y", "i"), ("ey", "e"), ("ei", "e")):
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", " ".join(s.split()))
    return s


EXTRA_NAMES = {5000: ["Jaffa", "Yafo", "יפו", "תל אביב", "ת״א"], 9000: ["Beersheba", "Beersheva", "ב״ש"], 8300: ["ראשל״צ"], 7900: ["פ״ת"], 6900: ["כפ״ס"], 7600: ["Akko", "Acre"], 8000: ["Tzfat", "Safed", "Zefat"], 6700: ["Tveria", "Teverya"], 7300: ["Natzrat"], 1200: ["Modiin"]}


@lru_cache(maxsize=1)
def _city_index() -> list[tuple[int, list[str], list[str]]]:
    """(code, Hebrew keys, English keys) of every official locality."""
    out = []
    for code, v in geo()["localities"].items():
        he, en = [v["he"]], [v["en"], v["official_en"], re.sub(r"\(.*?\)", "", v["en"])]
        for n in EXTRA_NAMES.get(code, []):
            (he if re.search(r"[א-ת]", n) else en).append(n)
        out.append((code, sorted({_key_he(n) for n in he}), sorted({_key_en(n) for n in en if n.strip()})))
    return out


def _city(code: int, counts: dict[int, int]) -> dict:
    v = geo()["localities"][code]
    return {"code": code, "name_he": v["he"], "name_en": v["en"], "garages": counts.get(code, 0)}


def search_cities(q: str, counts: dict[int, int] | None = None, limit: int = 8) -> list[dict]:
    """Localities whose Hebrew or English name starts with, contains or is very close to the text (bigger places, i.e. more garages, first)."""
    q = (q or "").strip()
    hebrew = bool(re.search(r"[א-ת]", q))
    key = _key_he(q) if hebrew else _key_en(q)
    counts = counts or {}
    if not q:                                                                           # nothing typed: the localities with most garages
        top = sorted(counts, key=lambda c: -counts[c])[:limit]
        return [_city(c, counts) for c in top]
    if len(key) < 2:
        return []
    scored = []
    for code, he, en in _city_index():
        names = he if hebrew else en
        score = max((4 if n == key else 3 if n.startswith(key) else 2 if f" {key}" in n else 0) for n in names)
        if score:
            scored.append((score, code))
    if not scored and len(key) >= 4:                                                    # a typing mistake: closest spellings only
        for code, he, en in _city_index():
            r = max(difflib.SequenceMatcher(None, key, n).ratio() for n in (he if hebrew else en))
            if r >= 0.8:
                scored.append((r, code))
    scored.sort(key=lambda x: (-x[0], -counts.get(x[1], 0), geo()["localities"][x[1]]["he"]))
    return [_city(c, counts) for _, c in scored[:limit]]


# ---------------------------------------------------------------- the official register
async def _page(client: httpx.AsyncClient, offset: int) -> dict:
    r = await client.get(URL, params={"resource_id": settings.gov_garages_resource_id, "limit": PAGE, "offset": offset})
    r.raise_for_status()
    return r.json()["result"]


async def download_register() -> list[dict]:
    """All rows of the official register (about 14,000: one per garage and trade)."""
    async with httpx.AsyncClient(timeout=25.0) as client:
        first = await _page(client, 0)
        rest = await asyncio.gather(*[_page(client, o) for o in range(PAGE, int(first["total"]), PAGE)])
    return first["records"] + [row for page in rest for row in page["records"]]


def _clean(s) -> str:
    return " ".join(str(s or "").split())


def build_garages(rows: list[dict]) -> list[dict]:
    """One entry per garage that has at least one trade for private cars. The name of the professional manager and the company number are not kept."""
    out: dict[int, dict] = {}
    for r in rows:
        service = SERVICE_OF_TRADE.get(_clean(r.get("miktzoa")))
        if service is None or r.get("mispar_mosah") is None:
            continue
        gid = int(r["mispar_mosah"])
        g = out.setdefault(gid, {"id": gid, "name": _clean(r.get("shem_mosah")), "address": _clean(r.get("ktovet")), "address_raw": r.get("ktovet") or "", "locality": _clean(r.get("yishuv")),
                                 "phone": _clean(r.get("telephone")), "services": []})
        if service not in g["services"]:
            g["services"].append(service)
    known = geo()["garages"]
    for g in out.values():
        k = known.get(g["id"], {})
        g["city_code"] = k.get("c") if k else None
        same_address = bool(k) and k.get("a") == g.pop("address_raw")
        if not same_address:
            g.pop("address_raw", None)
            hit = [c for c, he, _ in _city_index() if _key_he(g["locality"]) in he]
            g["city_code"] = hit[0] if hit else g["city_code"]
        g["services"].sort(key=SERVICES.index)
        g["phone"] = g["phone"] if len(re.sub(r"\D", "", g["phone"])) >= 8 else ""
        if same_address and "lat" in k:
            g.update({"lat": k["lat"], "lon": k["lon"], "position": k["p"]})
        else:
            g.update({"lat": None, "lon": None, "position": "none"})
        g["opening_hours"] = k.get("h") if same_address else None
    return list(out.values())


_memory: dict = {"at": 0.0, "value": None}
_lock = asyncio.Lock()


async def register() -> dict:
    """{"as_of": ISO time of the download, "stale": bool, "garages": [...]}"""
    if _memory["value"] is not None and time.monotonic() - _memory["at"] < MEMORY_SECONDS:
        return _memory["value"]
    async with _lock:
        if _memory["value"] is not None and time.monotonic() - _memory["at"] < MEMORY_SECONDS:
            return _memory["value"]
        value = None
        try:
            value = await get_cached(CACHE_KEY)
        except Exception:  # noqa: BLE001 - a cache problem must not hide the answer
            pass
        if value is None:
            try:
                rows = await download_register()
                value = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stale": False, "garages": build_garages(rows)}
                if not value["garages"]:
                    raise ValueError("empty register")
                try:
                    await set_cached(CACHE_KEY, value)
                    await set_cached(STALE_KEY, value, STALE_TTL)
                except Exception:  # noqa: BLE001
                    pass
            except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                try:
                    value = await get_cached(STALE_KEY)
                except Exception:  # noqa: BLE001
                    value = None
                if value is None:
                    raise GarageRegisterUnavailable(f"garage register unavailable ({type(exc).__name__})") from exc
                value["stale"] = True
        _memory.update(at=time.monotonic(), value=value)
        return value


def city_counts(garages: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for g in garages:
        if g["city_code"] is not None:
            counts[g["city_code"]] = counts.get(g["city_code"], 0) + 1
    return counts


# ---------------------------------------------------------------- search
_PO_BOX = re.compile(r"(ת\.?\s*ד\.?|תד'?)\s*:?\s*\d+|ד\.?\s?נ\.?\s*[א-ת ]*")


def links(g: dict) -> dict:
    """Route links. With an exact (house number) position the route goes to it; otherwise to the published address, which the map service resolves itself."""
    street = _clean(_PO_BOX.sub(" ", g["address"])).strip(" ,.-")
    place = ", ".join(x for x in ((street if g["position"] != "none" else f"{g['name']}, {street}" if street else g["name"]), g["city_he"] or g["locality"]) if x)
    if g["position"] == "house":
        google_dest, waze = f"{g['lat']},{g['lon']}", f"https://waze.com/ul?ll={g['lat']}%2C{g['lon']}&navigate=yes"
    else:
        google_dest, waze = quote(place), f"https://waze.com/ul?q={quote(place)}&navigate=yes"
    return {"google_maps_url": f"https://www.google.com/maps/dir/?api=1&destination={google_dest}", "waze_url": waze,
            "google_search_url": f"https://www.google.com/maps/search/?api=1&query={quote(' '.join(x for x in (g['name'], street, g['city_he'] or g['locality']) if x))}"}


def _present(g: dict, distance: float | None, in_city: bool | None) -> dict:
    loc = geo()["localities"].get(g["city_code"])
    item = {**{k: g[k] for k in ("id", "name", "address", "locality", "phone", "services", "lat", "lon", "position", "opening_hours")},
            "city_he": loc["he"] if loc else g["locality"], "city_en": loc["en"] if loc else g["locality"], "distance_km": None if distance is None else round(distance, 1), "in_city": in_city}
    return {**item, **links(item)}


def find(garages: list[dict], lat: float, lon: float, radius_km: float, service: str | None = None, city_code: int | None = None) -> list[dict]:
    """Garages around a point, nearest first. With `city_code` the garages of that city come first (all of them), then the surroundings within the radius.
    Garages without a known position belong to their locality: listed after the others of their group, without a distance."""
    localities = geo()["localities"]
    found = []
    for g in garages:
        if service and service not in g["services"]:
            continue
        in_city = city_code is not None and g["city_code"] == city_code
        if g["position"] != "none":
            d = distance_km(lat, lon, g["lat"], g["lon"])
            if in_city or d <= radius_km:
                found.append((0 if in_city or city_code is None else 1, 0, d, g, d, in_city))
        else:
            c = localities.get(g["city_code"])
            if c is None:
                continue
            d = distance_km(lat, lon, c["lat"], c["lon"])
            if in_city or d <= radius_km:
                found.append((0 if in_city or city_code is None else 1, 1, d, g, None, in_city))
    found.sort(key=lambda f: (f[0], f[1], f[2], f[3]["id"]) if city_code is not None else (f[1], f[2], f[3]["id"]))
    return [_present(g, d, in_city if city_code is not None else None) for _, _, _, g, d, in_city in found]
