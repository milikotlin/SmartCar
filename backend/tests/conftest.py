import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


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
