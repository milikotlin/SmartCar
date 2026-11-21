"""Mileage selection: "I know my car's mileage" (user-reported) against "I don't know" (Model 1 estimate), and what Model 2 receives in each case.

Real PostgreSQL and Redis; the government services are replaced by recorded real rows. The rules under test (docs/MILEAGE_SELECTION.md):
  * a typed mileage is USER-REPORTED: shown as such, never stored, never called a measurement;
  * Model 2 receives an odometer only if it is the odometer recorded at the last inspection, or a plausible user-reported value; the Model 1 estimate never enters Model 2;
  * a stored (recorded) odometer is never overwritten by an estimate or by a typed value.
"""
from datetime import date

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.database import async_session, engine
from app.main import app
from app.models import InspectionRecord, MaintenanceRecord, Vehicle
from app.redis_client import _redis
from app.services import gov_api, recalls

pytestmark = pytest.mark.asyncio(loop_scope="module")

PLATE = 4908732          # Toyota petrol 2015, private: covered by Model 2, aged 11
YOUNG = 43983303         # Kia hybrid 2023: 3 years old
EV = 88328404            # Tesla 2026: not covered by Model 2
PLATES = [str(p) for p in (PLATE, YOUNG, EV)]
KEY = {"X-Write-Key": "test-workshop-key"}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(registry_rows):
    by_plate = {str(r["mispar_rechev"]): r for r in registry_rows}

    async def fake_registry(plate):
        return by_plate.get(plate)

    async def fake_recalls(plate):
        return []

    gov_api.fetch_vehicle_record, recalls.fetch_open_recalls = fake_registry, fake_recalls
    await engine.dispose()
    await _redis.connection_pool.disconnect()
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate.in_(PLATES)))
        await s.commit()
    await _redis.delete(*[f"{k}:{p}" for k in ("vehicle", "recalls") for p in PLATES])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with async_session() as s:
        await s.execute(delete(Vehicle).where(Vehicle.license_plate.in_(PLATES)))
        await s.commit()
    await engine.dispose()
    await _redis.connection_pool.disconnect()


async def predict(client, plate, **params):
    r = await client.get(f"/api/v1/predict/{plate}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def stored_rows(plate) -> tuple[int, int, int]:
    async with async_session() as s:
        n = lambda m: select(func.count()).select_from(m).where(m.license_plate == str(plate))
        return ((await s.execute(n(Vehicle))).scalar_one(), (await s.execute(n(MaintenanceRecord))).scalar_one(), (await s.execute(n(InspectionRecord))).scalar_one())


# ------------------------------------------------------------------ option 2: automatic estimate (the default)
async def test_estimate_option_uses_model1_and_gives_model2_no_odometer(client):
    b = await predict(client, PLATE)
    m, r = b["mileage"], b["inspection_risk"]
    assert m["primary_source"] == "estimated" and m["primary_km"] == m["estimated_km"] and m["user_reported_km"] is None and m["measured_km"] is None
    assert not m["user_reported_used_by_model2"] and m["user_reported_note"] is None
    assert r["variant"] == "cold" and not r["uses_measured_odometer"] and r["odometer_source"] is None          # the estimate is NOT an input of Model 2
    assert m["estimate_reliability"] in ("ok", "low") and m["estimated_low_km"] <= m["estimated_km"] <= m["estimated_high_km"]


# ------------------------------------------------------------------ option 1: user-reported mileage
async def test_user_reported_mileage_is_labelled_not_stored_and_reaches_model2(client):
    before = await predict(client, PLATE)
    b = await predict(client, PLATE, odometer_km=123_456)
    m, r = b["mileage"], b["inspection_risk"]
    assert m["primary_source"] == "user_reported" and m["primary_km"] == 123_456 and m["user_reported_km"] == 123_456
    assert "has not been verified" in m["label"] and "not stored" in m["label"] and "Model 1 estimate for comparison" in m["label"]
    assert m["estimated_km"] == before["mileage"]["estimated_km"]                                    # Model 1 still computed and unchanged
    assert m["user_reported_used_by_model2"] and "approximation" in m["user_reported_note"] and "not verified" in m["user_reported_note"]
    assert r["variant"] == "cold_odo" and r["odometer_source"] == "user_reported" and r["uses_measured_odometer"]
    assert await stored_rows(PLATE) == (0, 0, 0)                                                      # nothing was written: no vehicle row, no record
    again = await predict(client, PLATE)                                                              # and the next view without it is back to the estimate
    assert again["mileage"]["primary_source"] == "estimated" and again["inspection_risk"]["variant"] == "cold" and again["inspection_risk"] == before["inspection_risk"]


async def test_model2_receives_exactly_the_typed_value_when_it_is_used(client):
    from app.ml.registry import get_models
    from app.ml.risk import RiskInputs
    from app.services import features
    from app.services.translation import translate_vehicle_record

    models = get_models()
    for km in (30_000, 123_456, 200_000):
        api = (await predict(client, PLATE, odometer_km=km))["inspection_risk"]
        profile = await gov_api.fetch_vehicle_record(str(PLATE))
        rx = features.risk_inputs(translate_vehicle_record(profile), None, km, None)
        direct = models.risk.predict(RiskInputs(age_year=rx.age_year, fuel=rx.fuel, make=rx.make, odometer_km=km))
        assert [s["level"] for s in api["systems"]] == [s.level for s in direct.systems], km


async def test_implausible_user_mileage_is_shown_but_not_given_to_model2(client):
    b = await predict(client, PLATE, odometer_km=900_000)                                             # 82,000 km per year for an 11-year-old car
    m, r = b["mileage"], b["inspection_risk"]
    assert m["primary_source"] == "user_reported" and m["primary_km"] == 900_000                       # still shown, as reported
    assert not m["user_reported_used_by_model2"] and "Not used by the risk model" in m["user_reported_note"] and "per year" in m["user_reported_note"]
    assert r["variant"] == "cold" and not r["uses_measured_odometer"] and r["odometer_source"] is None
    assert b["failure_risk"]["inputs"]["km"] == m["estimated_km"] and b["failure_risk"]["inputs"]["km_source"] == "estimated"    # nor by Model 2 (PDF)
    young = await predict(client, YOUNG, odometer_km=250_000)                                          # 83,000 km per year for a 3-year-old car
    assert not young["mileage"]["user_reported_used_by_model2"] and young["inspection_risk"]["variant"] == "cold"
    ok_young = await predict(client, YOUNG, odometer_km=45_000)
    assert ok_young["mileage"]["user_reported_used_by_model2"] and ok_young["inspection_risk"]["variant"] == "cold_odo"


async def test_vehicle_outside_model2_coverage_still_shows_the_reported_mileage_but_model2_is_not_used(client):
    b = await predict(client, EV, odometer_km=4_000)
    assert b["mileage"]["primary_source"] == "user_reported" and b["mileage"]["primary_km"] == 4_000
    assert not b["inspection_risk"]["covered"] and not b["mileage"]["user_reported_used_by_model2"] and "does not cover" in b["mileage"]["user_reported_note"]
    assert b["inspection_risk"]["odometer_source"] is None and not b["inspection_risk"]["uses_measured_odometer"]


async def test_invalid_mileage_is_rejected_by_the_api(client):
    for bad in ("-1", "0", "1000001", "abc", "12.5", "", "1e6", "99999999999999999999"):
        r = await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": bad})
        assert r.status_code == 422, bad
    assert (await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": 1})).status_code == 200
    assert (await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": 1_000_000})).status_code == 200


# ------------------------------------------------------------------ recorded odometers are never overwritten
async def test_a_recorded_inspection_odometer_wins_for_model2_and_nothing_overwrites_it(client):
    last = (await client.get(f"/api/v1/vehicles/{PLATE}")).json()["last_test_date"][:10]
    r = await client.post(f"/api/v1/vehicles/{PLATE}/inspections", json={"inspection_date": last, "odometer_km": 118_000, "brakes_defect": True}, headers=KEY)
    assert r.status_code == 201
    try:
        recorded = await predict(client, PLATE)
        assert recorded["mileage"]["primary_source"] == "measured" and recorded["mileage"]["primary_km"] == 118_000
        assert recorded["inspection_risk"]["variant"] == "hist_odo" and recorded["inspection_risk"]["odometer_source"] == "recorded_inspection"
        typed = await predict(client, PLATE, odometer_km=130_000)
        m = typed["mileage"]
        assert m["primary_source"] == "user_reported" and m["primary_km"] == 130_000 and m["measured_km"] == 118_000        # the recorded value is still there
        assert not m["user_reported_used_by_model2"] and "recorded at the last inspection" in m["user_reported_note"]
        assert typed["inspection_risk"] == recorded["inspection_risk"]                                                       # Model 2 saw the recorded odometer, not the typed one
        assert (await predict(client, PLATE))["mileage"]["primary_km"] == 118_000                          # back to the record, never to an estimate
        assert (await stored_rows(PLATE))[2] == 1                                                                            # the typed value created no record
    finally:
        async with async_session() as s:
            await s.execute(delete(Vehicle).where(Vehicle.license_plate == str(PLATE)))
            await s.commit()


async def test_a_service_record_is_kept_when_the_user_types_a_mileage(client):
    today = date.today().isoformat()
    r = await client.post(f"/api/v1/vehicles/{YOUNG}/maintenance", json={"service_date": today, "mileage_at_service": 41_000, "description": "Oil and filter change", "maintenance_category": "oil", "total_cost": "300"}, headers=KEY)
    assert r.status_code == 201
    typed = (await predict(client, YOUNG, odometer_km=50_000))["mileage"]
    assert typed["primary_source"] == "user_reported" and typed["measured_km"] == 41_000
    plain = (await predict(client, YOUNG))["mileage"]
    assert plain["primary_source"] == "measured" and plain["primary_km"] == 41_000 and plain["user_reported_km"] is None


# ------------------------------------------------------------------ the chat tells the language model where the number comes from
async def test_chat_facts_label_the_user_reported_mileage(client):
    from app.services import chat

    b = await client.get(f"/api/v1/predict/{PLATE}", params={"odometer_km": 123_456})
    from app.schemas.prediction import PredictionResponse

    facts = chat.facts(PredictionResponse(**b.json()), date.today())
    assert any("USER-REPORTED" in line and "not verified" in line for line in facts)
    r = await client.post("/api/v1/chat", json={"license_plate": str(PLATE), "message": "noise when braking", "odometer_km": 123_456})
    assert r.status_code == 200 and any("USER-REPORTED" in line for line in r.json()["context"])
    assert (await client.post("/api/v1/chat", json={"license_plate": str(PLATE), "message": "x", "odometer_km": -3})).status_code == 422
