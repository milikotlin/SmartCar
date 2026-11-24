"""Nearby garages: official register (recorded rows), city names in two languages, distances, privacy of the position, optional Google ratings. No test calls the internet."""
import asyncio
import json
import math

import httpx
import pytest

from app import security
from app.config import settings
from app.main import app
from app.services import garages, google_places

GEO = garages.geo()


def row(gid, trade="מכונאות רכב בנזין", name="מוסך בדיקה", address="המלאכה 1", locality="חולון", phone="03-1234567", **kw):
    return {"mispar_mosah": gid, "shem_mosah": name, "ktovet": address, "yishuv": locality, "telephone": phone, "miktzoa": trade, "menahel_miktzoa": "ישראל ישראלי", "rasham_havarot": 511111111, **kw}


def known(city, position, n=0):
    """A real garage of the position file: (licence number, its entry)."""
    return [(gid, g) for gid, g in sorted(GEO["garages"].items()) if g["c"] == city and g.get("p", "none") == position][n]


def rows_for(*found):
    return [row(gid, address=g["a"], locality=GEO["localities"][g["c"]]["he"], name=f"מוסך {gid}") for gid, g in found]


async def within_quota(*args):
    return True


@pytest.fixture
def fake_register(monkeypatch):
    """Replaces the download, the Redis cache and the in-process memory."""
    store: dict = {}
    calls = {"n": 0, "fail": False}
    (h1, h2), (s1,), (n1,), (far,) = [known(6600, "house", i) for i in (0, 1)], [known(6600, "street")], [known(6600, "none")], [known(4000, "house")]
    rows = rows_for(h1, h2, s1, n1, far) + [row(h1[0], "תיקון אחזקת רכב חשמלי/היברידי", address=h1[1]["a"], name=f"מוסך {h1[0]}"), row(99_999_999, "תיקון מלגזות הרמה"), row(99_999_998, address="רחוב שלא קיים 5")]

    async def download():
        calls["n"] += 1
        if calls["fail"]:
            raise httpx.ConnectTimeout("down")
        return rows

    async def get(key):
        return json.loads(store[key]) if key in store else None

    async def put(key, value, ttl=None):
        store[key] = json.dumps(value)

    monkeypatch.setattr(garages, "download_register", download)
    monkeypatch.setattr(garages, "get_cached", get)
    monkeypatch.setattr(garages, "set_cached", put)
    monkeypatch.setattr(garages, "_memory", {"at": 0.0, "value": None})
    monkeypatch.setattr(garages, "_lock", asyncio.Lock())
    monkeypatch.setattr(settings, "google_places_api_key", None)
    monkeypatch.setattr(security, "_hit", within_quota)          # no Redis connection is opened in these short event loops
    return {"store": store, "calls": calls, "house": h1, "house2": h2, "street": s1, "none": n1, "far": far, "rows": rows}


def call(*requests):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            return [await c.request(m, u, **kw) for m, u, kw in requests]

    return asyncio.run(run())


def get(url, **kw):
    return call(("GET", url, kw))[0]


# ---------------------------------------------------------------- the position file
def test_position_file_is_complete_and_inside_the_country():
    assert len(GEO["localities"]) > 1_200 and len(GEO["garages"]) > 5_000
    for v in GEO["localities"].values():
        assert 29.4 < v["lat"] < 33.4 and 34.2 < v["lon"] < 35.95 and v["he"] and v["en"]
    for g in GEO["garages"].values():
        assert ("lat" in g) == ("p" in g) and g.get("p") in (None, "house", "street")
        if "lat" in g:
            c = GEO["localities"][g["c"]]
            assert garages.distance_km(g["lat"], g["lon"], c["lat"], c["lon"]) < 16            # a position lies in the locality the register publishes
    assert "OpenStreetMap" in GEO["meta"]["geometry_source"] and "data.gov.il" in GEO["meta"]["garages_source"]


def test_city_centres_match_the_known_geography():
    for code, lat, lon in ((5000, 32.07, 34.78), (3000, 31.78, 35.21), (4000, 32.80, 34.99), (9000, 31.25, 34.79), (2600, 29.55, 34.95)):
        c = GEO["localities"][code]
        assert garages.distance_km(lat, lon, c["lat"], c["lon"]) < 3


def test_distance_is_the_great_circle():
    assert garages.distance_km(32.0, 34.8, 32.0, 34.8) == 0
    assert math.isclose(garages.distance_km(32.0853, 34.7818, 31.7683, 35.2137), 54, abs_tol=1)      # Tel Aviv - Jerusalem


# ---------------------------------------------------------------- city names
@pytest.mark.parametrize("text,code", [
    ("Tel Aviv", 5000), ("tel aviv-yafo", 5000), ("תל אביב", 5000), ("Jaffa", 5000), ("Jerusalem", 3000), ("ירושלים", 3000), ("Haifa", 4000), ("חיפה", 4000), ("Beer Sheva", 9000), ("Beersheba", 9000),
    ("באר שבע", 9000), ("Petah Tikva", 7900), ("Petach Tikva", 7900), ("PETAH TIQWA", 7900), ("פתח תקוה", 7900), ("פתח תקווה", 7900), ("Herzliya", 6400), ("הרצלייה", 6400), ("Kfar Saba", 6900), ("Kefar Sava", 6900),
    ("Rishon", 8300), ("ראשל\"צ", 8300), ("Kiryat Gat", 2630), ("קריית גת", 2630), ("Bnei Brak", 6100), ("Eilat", 2600), ("Acre", 7600), ("Akko", 7600), ("Tzfat", 8000), ("Modiin", 1200), ("Ashkelon", 7100),
    ("Ra'anana", 8700), ("raanana", 8700), ("jerusalm", 3000)])
def test_cities_are_found_in_english_and_hebrew(text, code):
    counts = {code: 10}
    assert garages.search_cities(text, counts)[0]["code"] == code


def test_unknown_and_empty_city_texts():
    assert garages.search_cities("Paris") == [] and garages.search_cities("פריז") == [] and garages.search_cities("x") == []
    assert [c["code"] for c in garages.search_cities("", {3000: 5, 4000: 9, 5000: 7}, 2)] == [4000, 5000]            # nothing typed: the places with most garages


# ---------------------------------------------------------------- the register
def test_register_keeps_only_private_car_garages_and_no_personal_names(fake_register):
    out = {g["id"]: g for g in garages.build_garages(fake_register["rows"])}
    assert 99_999_999 not in out                                                          # a forklift-only licence
    assert out[fake_register["house"][0]]["services"] == ["mechanics", "ev_hybrid"]        # one entry per garage, trades grouped
    assert "ישראל ישראלי" not in json.dumps(list(out.values()), ensure_ascii=False) and "511111111" not in json.dumps(list(out.values()))
    assert out[99_999_998]["position"] == "none" and out[99_999_998]["city_code"] == 6600  # a garage that is not in the position file yet: listed in its city, not on the map


def test_a_position_is_dropped_when_the_published_address_changed():
    gid, g = known(6600, "house")
    same, moved = (garages.build_garages([row(gid, address=a)])[0] for a in (g["a"], "כתובת חדשה 7"))
    assert same["position"] == "house" and same["lat"] == g["lat"]
    assert moved["position"] == "none" and moved["lat"] is None and moved["city_code"] == 6600


def test_every_listed_trade_belongs_to_a_service_of_the_filter():
    assert set(garages.SERVICE_OF_TRADE.values()) == set(garages.SERVICES)


# ---------------------------------------------------------------- search
def test_city_search_lists_the_city_first_and_says_it_is_approximate(fake_register):
    r = get("/api/v1/garages?city=6600&radius_km=10").json()
    assert r["mode"] == "city" and r["approximate"] is True and r["city"]["name_en"] == "Holon" and r["city"]["name_he"] == "חולון"
    ids = [g["id"] for g in r["items"]]
    assert set(ids) == {fake_register[k][0] for k in ("house", "house2", "street", "none")} | {99_999_998} and r["total_in_city"] == 5
    d = [g["distance_km"] for g in r["items"] if g["distance_km"] is not None]
    assert d == sorted(d) and all(g["distance_km"] is None and g["lat"] is None for g in r["items"] if g["position"] == "none")
    assert r["without_position"] == 2 and [g["position"] for g in r["items"]][-2:] == ["none", "none"]
    assert r["ratings_available"] is False and r["stale"] is False and "Ministry of Transport" in r["source"]


def test_surroundings_filter_and_paging(fake_register):
    all_ = get("/api/v1/garages?city=6600&radius_km=50").json()
    page = [get(f"/api/v1/garages?city=6600&radius_km=50&limit=2&offset={o}").json()["items"] for o in (0, 2, 4)]
    assert [g["id"] for p in page for g in p] == [g["id"] for g in all_["items"]]
    ev = get("/api/v1/garages?city=6600&service=ev_hybrid").json()
    assert [g["id"] for g in ev["items"]] == [fake_register["house"][0]]
    assert get("/api/v1/garages?city=6600&service=gearbox").json()["total"] == 0


def test_gps_search_sorts_by_the_real_distance(fake_register):
    h = fake_register["house2"][1]
    r = call(("POST", "/api/v1/garages/near", {"json": {"lat": h["lat"], "lon": h["lon"], "radius_km": 10}}))[0].json()
    assert r["mode"] == "gps" and r["approximate"] is False and r["city"] is None and r["centre"] is None
    assert r["items"][0]["distance_km"] == 0 and fake_register["far"][0] not in [g["id"] for g in r["items"]]
    d = [g["distance_km"] for g in r["items"] if g["distance_km"] is not None]
    assert d == sorted(d)


def test_gps_position_is_never_stored_cached_or_echoed(fake_register):
    r = call(("POST", "/api/v1/garages/near", {"json": {"lat": 32.01987, "lon": 34.78765, "radius_km": 10}}))[0]
    assert "32.01987" not in r.text and "34.78765" not in r.text
    assert set(fake_register["store"]) == {garages.CACHE_KEY, garages.STALE_KEY} and "32.01987" not in json.dumps(fake_register["store"])
    assert get("/api/v1/garages/near?lat=32&lon=34.8").status_code in (404, 405, 422)      # not accepted in the address


@pytest.mark.parametrize("body", [{"lat": 48.8, "lon": 2.3}, {"lat": 32.0}, {"lat": "x", "lon": 34.8}, {"lat": 32, "lon": 34.8, "radius_km": 500}, {"lat": 32, "lon": 34.8, "service": "'; drop table"}])
def test_invalid_positions_and_filters_are_rejected(fake_register, body):
    assert call(("POST", "/api/v1/garages/near", {"json": body}))[0].status_code == 422


def test_unknown_city_and_invalid_query(fake_register):
    assert get("/api/v1/garages?city=1").status_code == 404 and get("/api/v1/garages?city=abc").status_code == 422 and get("/api/v1/garages?city=6600&limit=1000").status_code == 422


def test_route_links(fake_register):
    items = {g["id"]: g for g in get("/api/v1/garages?city=6600").json()["items"]}
    house, street, none = (items[fake_register[k][0]] for k in ("house", "street", "none"))
    assert house["google_maps_url"].endswith(f"destination={house['lat']},{house['lon']}") and f"ll={house['lat']}%2C{house['lon']}" in house["waze_url"]
    for g in (street, none):                                                              # no exact point: the published address goes to the map service
        assert "destination=%D7" in g["google_maps_url"] and g["waze_url"].startswith("https://waze.com/ul?q=%D7") and "ll=" not in g["waze_url"]
    assert all(g["google_maps_url"].startswith("https://www.google.com/maps/") and g["google_search_url"].startswith("https://www.google.com/maps/") for g in items.values())


def test_a_post_box_is_not_sent_as_a_destination():
    g = {"name": "מוסך הצפון", "address": "ת.ד. 8105", "locality": "טייבה", "city_he": "טייבה", "position": "none", "lat": None, "lon": None}
    assert "8105" not in garages.links(g)["google_maps_url"] and "8105" not in garages.links(g)["waze_url"]


# ---------------------------------------------------------------- cache and failures
def test_register_is_downloaded_once_and_cached(fake_register):
    get("/api/v1/garages?city=6600")
    get("/api/v1/garages?city=4000")
    garages._memory.update(at=0.0, value=None)                                            # another worker: read from Redis, not from the internet
    get("/api/v1/garages?city=6600")
    assert fake_register["calls"]["n"] == 1


def test_outage_uses_the_stored_copy_and_says_so(fake_register):
    get("/api/v1/garages?city=6600")
    fake_register["store"].pop(garages.CACHE_KEY)
    garages._memory.update(at=0.0, value=None)
    fake_register["calls"]["fail"] = True
    r = get("/api/v1/garages?city=6600").json()
    assert r["stale"] is True and r["total"] == 5


def test_outage_without_a_copy_is_503_never_invented_results(fake_register):
    fake_register["calls"]["fail"] = True
    r = get("/api/v1/garages?city=6600")
    assert r.status_code == 503 and "ConnectTimeout" in r.text and get("/api/v1/garages/cities?q=holon").status_code == 503


def test_redis_down_does_not_hide_the_garages(fake_register, monkeypatch):
    async def broken(*a, **k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(garages, "get_cached", broken)
    monkeypatch.setattr(garages, "set_cached", broken)
    assert get("/api/v1/garages?city=6600").json()["total"] == 5


def test_garages_are_rate_limited(fake_register, monkeypatch):
    async def over(*a):
        return False

    monkeypatch.setattr(security, "_hit", over)
    assert get("/api/v1/garages/cities").status_code == 429


# ---------------------------------------------------------------- optional Google ratings
PLACE = {"displayName": {"text": "מוסך לדוגמה"}, "formattedAddress": "המלאכה 1, חולון", "location": {"latitude": 32.0, "longitude": 34.8}, "rating": 4.4, "userRatingCount": 87,
         "regularOpeningHours": {"weekdayDescriptions": ["Sunday: 8:00 AM – 5:00 PM"]}, "nationalPhoneNumber": "03-123-4567", "googleMapsUri": "https://maps.google.com/?cid=1"}
GARAGE = {"id": 1, "name": "מוסך לדוגמה בע מ", "address": "המלאכה 1", "city_he": "חולון", "phone": "03-1234567", "position": "house", "lat": 32.0, "lon": 34.8}


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-google-key")

    async def allowed():
        return True

    monkeypatch.setattr(google_places, "_within_daily_limit", allowed)


def google(answer, status=200, seen=None):
    def handler(request):
        if seen is not None:
            seen.update(headers=dict(request.headers), body=json.loads(request.content), url=str(request.url))
        return httpx.Response(status, json=answer)

    return httpx.MockTransport(handler)


def test_without_a_key_ratings_are_off(fake_register):
    assert get("/api/v1/garages/1/google").status_code == 404


def test_google_rating_of_the_same_business(with_key):
    seen = {}
    d = asyncio.run(google_places.details(GARAGE, "he", google({"places": [PLACE]}, seen=seen)))
    assert d["rating"] == 4.4 and d["rating_count"] == 87 and d["opening_hours"] and d["attribution"] == "Google Maps"
    assert seen["headers"]["x-goog-api-key"] == "test-google-key" and "test-google-key" not in seen["url"] and "places.rating" in seen["headers"]["x-goog-fieldmask"]
    assert seen["body"]["languageCode"] == "he" and seen["body"]["regionCode"] == "IL"


@pytest.mark.parametrize("change", [{"nationalPhoneNumber": "03-999-9999", "displayName": {"text": "פיצה הצפון"}}, {"nationalPhoneNumber": None, "location": {"latitude": 32.2, "longitude": 34.8}}])
def test_another_business_is_never_shown_as_this_garage(with_key, change):
    assert asyncio.run(google_places.details(GARAGE, "en", google({"places": [{**PLACE, **change}]}))) is None
    assert asyncio.run(google_places.details(GARAGE, "en", google({}))) is None


def test_daily_limit_and_failed_counter_stop_paid_calls(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-google-key")

    class Down:
        async def incr(self, key):
            raise ConnectionError("redis down")

    monkeypatch.setattr(google_places, "_redis", Down())
    with pytest.raises(google_places.PlacesQuotaExceeded):
        asyncio.run(google_places.details(GARAGE, "en", google({"places": [PLACE]})))

    class Counter:
        n = 0

        async def incr(self, key):
            self.n += 1
            return self.n

        async def expire(self, key, seconds):
            return True

    monkeypatch.setattr(google_places, "_redis", Counter())
    monkeypatch.setattr(settings, "google_places_daily_limit", 1)
    assert asyncio.run(google_places.details(GARAGE, "en", google({"places": [PLACE]})))["rating"] == 4.4
    with pytest.raises(google_places.PlacesQuotaExceeded):
        asyncio.run(google_places.details(GARAGE, "en", google({"places": [PLACE]})))


def test_google_errors_never_reveal_the_key(fake_register, with_key, monkeypatch):
    real = google_places.details

    async def failing(g, lang):
        return await real(g, lang, google({"error": {"message": "API key test-google-key invalid"}}, 403))

    monkeypatch.setattr(google_places, "details", failing)
    r = get(f"/api/v1/garages/{fake_register['house'][0]}/google")
    assert r.status_code == 503 and "test-google-key" not in r.text
    assert get("/api/v1/garages/987654321/google").status_code == 404
    assert get("/api/v1/garages?city=6600").json()["ratings_available"] is True
