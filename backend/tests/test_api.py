"""API tests: FastAPI app with the real PostgreSQL and Redis of the compose stack; only the two government HTTP services are replaced by recorded real rows."""
from datetime import date

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.config import settings
from app.database import async_session
from app.main import app
from app.models import Vehicle
from app.redis_client import _redis
from app.services import gov_api, recalls

pytestmark = pytest.mark.asyncio(loop_scope="module")

PLATE = 4908732          # Toyota petrol 2015, private (real registry row from the fixtures)
HYBRID = 43983303        # Kia hybrid 2023, leasing
EV = 88328404            # Tesla 2026
RECALL_ROW = {"MISPAR_RECHEV": PLATE, "RECALL_ID": 1, "SUG_RECALL": "תקלה סידרתית בטיחותית", "SUG_TAKALA": "בלמים", "TEUR_TAKALA": "דוגמה", "TAARICH_PTICHA": "2024-12-03"}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(registry_rows):
    by_plate = {str(r["mispar_rechev"]): r for r in registry_rows}

    async def fake_registry(plate):
        return by_plate.get(plate)

    async def fake_recalls(plate):
        return [recalls.translate_recall(RECALL_ROW)] if plate == str(PLATE) else []

    gov_api.fetch_vehicle_record, recalls.fetch_open_recalls = fake_registry, fake_recalls
    settings.openai_api_key = None
    plates = [str(p) for p in (PLATE, HYBRID, EV)]
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate.in_(plates)))
        await s.commit()
    await _redis.delete(*[f"{k}:{p}" for k in ("vehicle", "recalls") for p in plates])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate.in_(plates)))
        await s.commit()


async def test_health_and_models_are_loaded(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_vehicle_profile_is_translated(client):
    r = await client.get(f"/api/v1/vehicles/{PLATE}")
    assert r.status_code == 200
    body = r.json()
    assert body["make"] == "Toyota" and body["fuel_type"] == "Petrol" and body["ownership"] == "Private" and body["manufacture_year"] == 2015
    assert body["license_valid_until"] and body["last_test_date"]


@pytest.mark.parametrize("plate", ["123456", "123456789", "abc12345", "1234567a"])
async def test_invalid_plates_are_rejected(client, plate):
    assert (await client.get(f"/api/v1/vehicles/{plate}")).status_code == 422
    assert (await client.get(f"/api/v1/predict/{plate}")).status_code == 422


async def test_unknown_plate_is_404(client):
    assert (await client.get("/api/v1/vehicles/10000001")).status_code == 404
    assert (await client.get("/api/v1/predict/10000001")).status_code == 404
    assert (await client.post("/api/v1/chat", json={"license_plate": "10000001", "message": "hi"})).status_code == 404


async def test_prediction_without_any_records(client):
    r = await client.get(f"/api/v1/predict/{PLATE}")
    assert r.status_code == 200
    b = r.json()
    m = b["mileage"]
    assert m["primary_source"] == "estimated" and m["estimated_low_km"] <= m["estimated_km"] <= m["estimated_high_km"] and "not a measurement" in m["label"]
    risk = b["inspection_risk"]
    assert risk["covered"] and risk["variant"] == "cold" and not risk["uses_history"] and not risk["uses_measured_odometer"]
    assert [s["system"] for s in risk["systems"]] == ["brakes", "electrical", "engine_emissions"]
    assert "not been validated on Israeli" in risk["definition"] and "not probabilities of failure" in risk["disclaimer"]
    for s in risk["systems"]:
        assert s["level"] in ("low", "moderate", "high") and s["same_age_label"] in ("lower", "typical", "higher") and 5 <= s["higher_than_of_100"] <= 95 and s["higher_than_of_100"] % 5 == 0
        assert set(s["observed_in_reference"]) == {"low", "moderate", "high"} and s["observed_in_reference"]["low"] < s["observed_in_reference"]["high"]
        assert "foreign_probability" not in s and "relative_risk" not in s and "percentile_same_age" not in s      # no probability, no "times the average"
    assert risk["scale"]["interval"].startswith("Standard interval of 12 months") and set(risk["scale"]["cut_percentiles"]) == {"brakes", "electrical", "engine_emissions"}
    # the three kinds of statements are kept apart
    assert b["maintenance"]["kind"] == "recommended_maintenance" and b["recalls"]["kind"] == "official_recall" and risk["kind"] == "estimated_inspection_defect_risk"
    assert b["recalls"]["available"] and b["recalls"]["count"] == 1 and b["recalls"]["items"][0]["related_system"] == "brakes"
    assert "Generic service intervals" in b["maintenance"]["disclaimer"]


async def test_measured_odometer_replaces_the_estimate_and_selects_the_odometer_variant(client):
    b = (await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": 123_456})).json()
    assert b["mileage"]["primary_source"] == "measured" and b["mileage"]["primary_km"] == 123_456 and b["mileage"]["estimated_km"] != 123_456
    assert b["inspection_risk"]["variant"] == "cold_odo" and b["inspection_risk"]["uses_measured_odometer"]
    assert b["maintenance"]["odometer_basis"] == "measured"
    assert (await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": -5})).status_code == 422


async def test_electric_vehicle_is_not_covered_by_model2_but_still_has_the_other_sections(client):
    b = (await client.get(f"/api/v1/predict/{EV}")).json()
    assert not b["inspection_risk"]["covered"] and b["inspection_risk"]["systems"] == []
    assert any("fuel type" in x or "age" in x for x in b["inspection_risk"]["reasons"])
    assert b["mileage"]["estimated_km"] >= 0 and b["maintenance"]["rules"]


async def test_inspection_history_is_used_only_when_it_is_the_last_registry_test(client):
    profile = (await client.get(f"/api/v1/vehicles/{PLATE}")).json()
    last = profile["last_test_date"][:10]
    # an old inspection that is not the last annual test: stored, but NOT used by the model
    old = await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": "2019-03-01", "brakes_defect": True})
    assert old.status_code == 201
    b = (await client.get(f"/api/v1/predict/{PLATE}")).json()
    assert b["inspection_risk"]["variant"] == "cold" and not b["history"]["history_used_by_model"] and "not the last annual test" in b["history"]["note"]
    # the last annual test with a brake defect and its odometer: history + measured odometer variant
    ok = await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": last, "odometer_km": 118_000, "brakes_defect": True})
    assert ok.status_code == 201
    dup = await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": last, "brakes_defect": False})
    assert dup.status_code == 409
    b2 = (await client.get(f"/api/v1/predict/{PLATE}")).json()
    assert b2["inspection_risk"]["variant"] == "hist_odo" and b2["history"]["history_used_by_model"] and b2["inspection_risk"]["uses_measured_odometer"]
    assert b2["mileage"]["primary_source"] == "measured" and b2["mileage"]["primary_km"] == 118_000
    assert all(s["level"] in ("low", "moderate", "high") for s in b2["inspection_risk"]["systems"])
    listing = (await client.get(f"/api/v1/vehicles/{PLATE}/inspections")).json()
    assert len(listing) == 2 and listing[0]["inspection_date"] >= listing[1]["inspection_date"]


async def test_maintenance_records_drive_the_rules_and_are_not_treated_as_inspections(client):
    before = (await client.get(f"/api/v1/predict/{HYBRID}")).json()
    assert before["history"]["maintenance_records"] == 0 and before["inspection_risk"]["variant"] == "cold"
    today = date.today().isoformat()
    r = await client.post(f"/api/v1/vehicles/{HYBRID}/maintenance",
                          json={"service_date": today, "mileage_at_service": 41_000, "description": "Replaced front brake pads", "maintenance_category": "brakes", "total_cost": "950.00"})
    assert r.status_code == 201 and r.json()["record_id"] > 0
    after = (await client.get(f"/api/v1/predict/{HYBRID}")).json()
    brakes = next(x for x in after["maintenance"]["rules"] if x["key"] == "brakes")
    assert brakes["status"] == "ok" and brakes["last_service_km"] == 41_000
    assert after["history"]["maintenance_records"] == 1 and after["inspection_risk"]["variant"] == "cold"     # a service record does not become inspection history
    assert after["mileage"]["primary_source"] == "measured" and after["mileage"]["primary_km"] == 41_000
    rows = (await client.get(f"/api/v1/vehicles/{HYBRID}/maintenance")).json()
    assert len(rows) == 1 and rows[0]["description"].startswith("Replaced front")
    assert (await client.post(f"/api/v1/vehicles/{HYBRID}/maintenance", json={"service_date": today, "mileage_at_service": -1, "description": "x"})).status_code == 422


async def test_chat_endpoint_answers_from_the_pipeline_facts(client):
    r = await client.post("/api/v1/chat", json={"license_plate": str(PLATE), "message": "Hearing a squeaking noise when braking"})
    assert r.status_code == 200
    b = r.json()
    assert b["source"] == "deterministic_fallback" and "brake" in b["answer"].lower() and any("Toyota" in c for c in b["context"])
    assert (await client.post("/api/v1/chat", json={"license_plate": str(PLATE), "message": ""})).status_code == 422
    assert (await client.post("/api/v1/chat", json={"license_plate": str(PLATE), "message": "x" * 1001})).status_code == 422


async def test_registry_outage_is_reported_as_503_not_a_crash(client, monkeypatch):
    async def down(plate):
        raise gov_api.RegistryUnavailableError("registry unavailable (ReadTimeout)")

    monkeypatch.setattr(gov_api, "fetch_vehicle_record", down)
    await _redis.delete("vehicle:55555555", "recalls:55555555")
    for path in ("/api/v1/vehicles/55555555", "/api/v1/predict/55555555"):
        r = await client.get(path)
        assert r.status_code == 503 and "temporarily unavailable" in r.json()["detail"]
    r = await client.post("/api/v1/chat", json={"license_plate": "55555555", "message": "hi"})
    assert r.status_code == 503
