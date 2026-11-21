"""Official data for Model 1 that the registry record lacks: engine size and transmission (model table) and number of owners (ownership history)."""
import pytest

from app.services import vehicle_specs



@pytest.mark.asyncio
async def test_engine_transmission_and_owners_from_the_official_tables(monkeypatch):
    async def recorded(resource, filters, limit=50):          # rows recorded from data.gov.il for the Toyota Auris hybrid 2015 (tozeret 430, degem 12)
        if resource == vehicle_specs.WLTP_RESOURCE:
            return [{"nefah_manoa": 1798, "automatic_ind": 1, "kinuy_mishari": "AURIS HYBRID"}]
        return [{"baalut_dt": 201804, "baalut": "פרטי"}, {"baalut_dt": 202202, "baalut": "פרטי"}]

    async def no_cache(key):
        return None

    async def store(key, value, ttl_seconds=None):
        return None

    monkeypatch.setattr(vehicle_specs, "_search", recorded)
    monkeypatch.setattr(vehicle_specs, "get_cached", no_cache)
    monkeypatch.setattr(vehicle_specs, "set_cached", store)
    s = await vehicle_specs.get_vehicle_specs("4908732", 430, 12, 2015)
    assert s.engine_cc == 1798.0 and s.automatic == 1.0 and vehicle_specs.owner_count(s) == 2     # one row per ownership, the first included


@pytest.mark.asyncio
async def test_unavailable_tables_give_unknown_never_an_invented_value(monkeypatch):
    async def down(resource, filters, limit=50):
        return None

    async def no_cache(key):
        return None

    async def store(key, value, ttl_seconds=None):
        raise AssertionError("an incomplete answer must not be cached")

    monkeypatch.setattr(vehicle_specs, "_search", down)
    monkeypatch.setattr(vehicle_specs, "get_cached", no_cache)
    monkeypatch.setattr(vehicle_specs, "set_cached", store)
    s = await vehicle_specs.get_vehicle_specs("4908732", 430, 12, 2015)
    assert s.engine_cc is None and s.automatic is None and vehicle_specs.owner_count(s) is None


def test_no_ownership_row_means_unknown_owner_type():
    assert vehicle_specs.owner_count(vehicle_specs.VehicleSpecs(owner_changes=0)) is None
    assert vehicle_specs.owner_count(vehicle_specs.VehicleSpecs(owner_changes=1)) == 1
