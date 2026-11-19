import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TEST_WRITE_KEY = "test-workshop-key"            # test value only: the real key lives in .env and is never read by the tests


@pytest.fixture(autouse=True)
def _security_settings():
    """Functional suites run with a known test key and generous rate limits; test_security.py tightens them on purpose."""
    from app.config import settings

    saved = (settings.records_write_key, settings.write_rate_per_minute, settings.chat_rate_per_minute)
    settings.records_write_key, settings.write_rate_per_minute, settings.chat_rate_per_minute = TEST_WRITE_KEY, 100_000, 100_000
    yield
    settings.records_write_key, settings.write_rate_per_minute, settings.chat_rate_per_minute = saved


@pytest.fixture(scope="session")
def registry_rows() -> list[dict]:
    """Real rows of the Ministry of Transport vehicle registry (public data), picked to cover makes, fuels, ownerships and ages."""
    return json.loads((FIXTURES / "registry_rows.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def models():
    from app.ml.registry import get_models

    return get_models()


@pytest.fixture(scope="session")
def profiles(registry_rows):
    from app.services.translation import translate_vehicle_record

    return {r["mispar_rechev"]: translate_vehicle_record(r) for r in registry_rows}
