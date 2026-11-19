"""Security of the write endpoints and the chat: workshop key, rate limit, CORS, record validation and quotas.

Real PostgreSQL and Redis of the compose stack; only the government HTTP services are replaced by recorded real rows. The key used here is a test value."""
from datetime import date, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.config import settings
from app.database import async_session, engine
from app.main import app
from app.models import InspectionRecord, MaintenanceRecord, Vehicle
from app.redis_client import _redis
from app.services import gov_api, recalls

pytestmark = pytest.mark.asyncio(loop_scope="module")

PLATE = "4908732"                 # Toyota petrol 2015 (real registry row from the fixtures)
KEY = "test-workshop-key"
TEST_IP = ("10.99.99.99", 5000)   # the rate limiter is keyed by client address: this suite uses its own
MAINT = {"service_date": date.today().isoformat(), "mileage_at_service": 50_000, "description": "Oil and filter change", "maintenance_category": "oil", "total_cost": "300"}


async def _count(model) -> int:
    async with async_session() as s:
        return (await s.execute(select(func.count()).select_from(model).where(model.license_plate == PLATE))).scalar_one()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(registry_rows):
    by_plate = {str(r["mispar_rechev"]): r for r in registry_rows}

    async def fake_registry(plate):
        return by_plate.get(plate)

    async def fake_recalls(plate):
        return []

    gov_api.fetch_vehicle_record, recalls.fetch_open_recalls = fake_registry, fake_recalls
    settings.openai_api_key = None
    await engine.dispose()
    await _redis.connection_pool.disconnect()
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate == PLATE))
        await s.commit()
    await _redis.delete(*[f"{k}:{PLATE}" for k in ("vehicle", "recalls")], "ratelimit:write:10.99.99.99", "ratelimit:chat:10.99.99.99")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=TEST_IP), base_url="http://test") as c:       # no default key on purpose
        yield c
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate == PLATE))
        await s.commit()
    await _redis.delete("ratelimit:write:10.99.99.99", "ratelimit:chat:10.99.99.99")
    await engine.dispose()
    await _redis.connection_pool.disconnect()


async def test_write_without_key_is_refused_and_stores_nothing(client):
    r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT)
    assert r.status_code == 401
    r2 = await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": date.today().isoformat(), "brakes_defect": True})
    assert r2.status_code == 401
    assert await _count(MaintenanceRecord) == 0 and await _count(InspectionRecord) == 0
    async with async_session() as s:
        assert await s.get(Vehicle, PLATE) is None            # not even the vehicle row is created by a refused request


async def test_write_with_wrong_key_is_refused(client):
    for bad in ("", "wrong", KEY + "x", KEY[:-1]):
        r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": bad})
        assert r.status_code == 401
    assert "key" in r.json()["detail"].lower() and KEY not in r.text            # the answer never echoes the key


async def test_write_with_the_right_key_works_and_reading_stays_open(client):
    r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": KEY})
    assert r.status_code == 201
    assert (await client.get(f"/api/v1/vehicles/{PLATE}/maintenance")).status_code == 200      # no key needed to read
    assert (await client.get(f"/api/v1/predict/{PLATE}")).status_code == 200


async def test_without_a_configured_key_writing_is_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "records_write_key", None)
    r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": KEY})
    assert r.status_code == 403 and "disabled" in r.json()["detail"]
    monkeypatch.setattr(settings, "records_write_key", "")
    assert (await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": ""})).status_code == 403     # an empty key is never a valid key


async def test_dates_must_be_plausible(client):
    h = {"X-Write-Key": KEY}
    future = (date.today() + timedelta(days=2)).isoformat()
    assert (await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json={**MAINT, "service_date": future}, headers=h)).status_code == 422
    assert (await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": future}, headers=h)).status_code == 422
    assert (await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json={**MAINT, "service_date": "1900-01-01"}, headers=h)).status_code == 422
    before_build = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json={**MAINT, "service_date": "2010-06-01"}, headers=h)      # the Toyota is a 2015 vehicle
    assert before_build.status_code == 422 and "manufacture" in before_build.json()["detail"]


async def test_per_vehicle_quota_limits_flooding(client, monkeypatch):
    h = {"X-Write-Key": KEY}
    n = await _count(MaintenanceRecord)
    monkeypatch.setattr(settings, "max_maintenance_per_plate", n + 1)
    assert (await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers=h)).status_code == 201
    r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers=h)
    assert r.status_code == 409 and "maximum" in r.json()["detail"]


async def test_rate_limit_throttles_writes_including_wrong_keys(client, monkeypatch):
    await _redis.delete("ratelimit:write:10.99.99.99")
    monkeypatch.setattr(settings, "write_rate_per_minute", 3)
    codes = [(await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": "guess"})).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 429, 429]               # guessing the key is throttled
    r = await client.post(f"/api/v1/vehicles/{PLATE}/maintenance", json=MAINT, headers={"X-Write-Key": KEY})
    assert r.status_code == 429 and r.headers["Retry-After"] == "60"
    await _redis.delete("ratelimit:write:10.99.99.99")


async def test_rate_limit_protects_the_paid_chat_endpoint(client, monkeypatch):
    await _redis.delete("ratelimit:chat:10.99.99.99")
    monkeypatch.setattr(settings, "chat_rate_per_minute", 2)
    body = {"license_plate": PLATE, "message": "squeaking when braking"}
    codes = [(await client.post("/api/v1/chat", json=body)).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    await _redis.delete("ratelimit:chat:10.99.99.99")


async def test_cors_allows_only_the_dashboard(client):
    ok = await client.options(f"/api/v1/vehicles/{PLATE}/maintenance", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-write-key"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000" and "x-write-key" in ok.headers.get("access-control-allow-headers", "").lower()
    evil = await client.options(f"/api/v1/vehicles/{PLATE}/maintenance", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers
    simple = await client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers
