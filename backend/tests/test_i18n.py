"""English / Hebrew answers: every text is translated, nothing else changes."""
import asyncio
import json
import re
from datetime import date

import httpx
import pytest

from app.config import settings
from app.i18n import domain
from app.i18n.chat_texts import TEXTS as CHAT
from app.i18n.localize import localize_prediction, localize_vehicle
from app.schemas.prediction import RecallInfo, RecallItem
from app.services import chat, prediction as pred, recalls
from app.services.prediction import build_prediction
from app.services.translation import translate_vehicle_record

TODAY = date(2026, 11, 24)
HEBREW = re.compile(r"[א-ת]")
# fields whose value is the same in both languages: identifiers, codes, dates, published names, the plate
LANGUAGE_FREE = {"license_plate", "trim_level", "make_raw", "color_raw", "last_test_date", "license_valid_until", "first_registration", "kind", "branch", "level", "system", "same_age_label",
                 "variant", "odometer_source", "key", "status", "source_kind", "estimate_reliability", "estimate_reliability_code", "reason_codes", "odometer_basis_code", "primary_source", "measured_as_of",
                 "last_service_date", "opened", "description_he", "related_system", "latest_inspection_date", "model1_version", "model2_version", "km_source", "make_model", "owner_type", "fuel"}


@pytest.fixture(scope="module", autouse=True)
def _no_cache():
    """These tests run many short event loops: no Redis connection is opened in them."""
    from app.services import vehicle_specs

    async def nothing(*args, **kw):
        return None

    with pytest.MonkeyPatch.context() as m:
        m.setattr(vehicle_specs, "get_cached", nothing)
        m.setattr(vehicle_specs, "set_cached", nothing)
        yield


def walk(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, (*path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, (*path, i))
    else:
        yield path, o


def language_free(path):
    return path == ("vehicle", "model") or next(k for k in reversed(path) if isinstance(k, str)) in LANGUAGE_FREE


def predict(profile, models, **kw):
    kw.setdefault("recalls_info", RecallInfo(available=False, error="recall service unavailable (ConnectTimeout)"))
    return asyncio.run(build_prediction(profile, models, None, today=TODAY, **kw))


@pytest.fixture(scope="module")
def answers(profiles, models):
    """Every fixture vehicle in several situations: automatic estimate, plausible and implausible typed mileage, other ages and fuels, recalls."""
    out = []
    recall = RecallInfo(available=True, count=2, items=[RecallItem(**recalls.translate_recall({"RECALL_ID": 1, "SUG_RECALL": "תקלה סידרתית בטיחותית", "SUG_TAKALA": c, "TEUR_TAKALA": "x"})) for c in ("בלמים", "כריות אוויר")])
    for p in profiles.values():
        out += [predict(p, models), predict(p, models, odometer_km=90_000, recalls_info=recall), predict(p, models, odometer_km=999_999)]
    some = next(iter(profiles.values()))
    for fuel in ("Petrol", "Diesel", "Hybrid", "Electric", "LPG/CNG", "מימן"):
        for year in (TODAY.year, TODAY.year - 2, TODAY.year - 9, TODAY.year - 16, TODAY.year - 28, TODAY.year - 45):
            p = some.model_copy(update={"fuel_type": fuel, "manufacture_year": year, "first_registration": None, "last_test_date": f"{TODAY.year}-01-10T00:00:00", "ownership": "Public" if year % 2 else "Rental", "make": "Zastava"})
            out.append(predict(p, models))
    return out


def test_english_answers_are_exactly_what_the_pipeline_wrote(answers):
    added = {"estimate_reliability_code", "reason_codes", "odometer_basis_code", "interval_months", "interval_km"}
    strip = lambda o: {k: strip(v) for k, v in o.items() if k not in added} if isinstance(o, dict) else [strip(v) for v in o] if isinstance(o, list) else o
    for a in answers:
        assert strip(localize_prediction(a, "en").model_dump()) == strip(a.model_dump())


def test_hebrew_changes_texts_only(answers):
    """Same structure, same numbers, flags, levels, codes and dates; only text fields differ."""
    for a in answers:
        en, he = (dict(walk(localize_prediction(a, lang).model_dump())) for lang in ("en", "he"))
        assert en.keys() == he.keys()
        for path, v in en.items():
            if not isinstance(v, str) or language_free(path):
                assert he[path] == v, path


def test_no_english_sentence_is_left_in_a_hebrew_answer(answers):
    left = set()
    for a in answers:
        for path, v in walk(localize_prediction(a, "he").model_dump()):
            if isinstance(v, str) and v and not language_free(path) and path[-1] != "source" and not HEBREW.search(v):
                left.add((".".join(map(str, path)), v))
    assert left == set()


def test_every_text_of_the_pipeline_has_a_known_code(answers):
    seen = {c for a in answers for path, v in walk(a.model_dump()) if isinstance(v, str) for c in [domain.code(v)] if c}
    # the situations above reach every reliability reason, coverage reason, typed-mileage note and data note that does not need a stored record
    assert {"m1_no_ev_statistics", "m1_unknown_fuel", "m1_old_for_fuel", "m1_imputed", "m1_beyond_data", "m1_ownership_unknown", "not_covered_fuel", "not_covered_young", "not_covered_old", "km_used", "km_implausible",
            "km_not_covered", "quality_auc", "cmp_model", "odo_estimated", "odo_reported", "basis_no_record_age", "recall_unavailable", "failure_branch_ice", "failure_branch_ev"} <= seen
    for code, _, he in domain.TEXTS:
        assert callable(he) or HEBREW.search(he), code
    assert len({c for c, _, _ in domain.TEXTS}) == len(domain.TEXTS)


@pytest.mark.parametrize("text,code", [
    ("too few real LPG/CNG vehicles of this age (12) support the estimate", "m1_too_few"),
    ("the model implies about 45,000 km per year, above every official group average: the official average for this age and ownership is shown instead", "m1_official_average"),
    ("Measured odometer 61,000 km as of 2026-01-15 (from a service or inspection record). Model 1 estimate for comparison: 90,000 km (indicative 80% range 50,000-120,000).", "m1_label_measured"),
    ("Used by Model 2 as the mileage. Not used by the comparison model: it uses the odometer recorded at the last inspection instead, which is the value it was trained on.", "km_recorded_wins"),
    ("the latest recorded inspection (2024-01-15) is not the last annual test of the registry (2026-06-24): history variant not used", "history_mismatch"),
    ("the latest recorded inspection (2024-01-15) is not the last annual test: history variant not used", "history_mismatch_plain"),
    ("measured odometer 60,000 km with no brake system inspection (pads, discs, lines) on record", "basis_no_record_km"),
    ("time and measured odometer", "basis_measured"), ("measured", "odo_measured"), ("failure-risk model unavailable (ValueError)", "model2_down"), ("history store unavailable (OperationalError)", "history_down")])
def test_texts_that_need_stored_records(text, code):
    assert domain.code(text) == code and HEBREW.search(domain.he(text)) and not re.search(r"\b(the|of|is|with)\b", domain.he(text))


def test_every_maintenance_rule_and_recall_category_has_hebrew():
    from app.services.maintenance_rules import RULES

    assert {r.key for r in RULES} == set(domain.RULE_LABEL) == set(domain.RULE_ADVICE) and {r.label.lower() for r in RULES} == set(domain.RULE_LABEL_EN_LOWER)
    assert set(domain.RECALL_CATEGORY) == set(recalls.CATEGORY_EN.values()) and len(domain.RECALL_CATEGORY) == len(recalls.CATEGORY_EN)


def test_an_unknown_text_is_returned_unchanged_never_guessed():
    assert domain.he("a sentence nobody wrote") == "a sentence nobody wrote" and domain.code("a sentence nobody wrote") is None and domain.he(None) is None


def test_vehicle_values_come_from_the_registry_in_hebrew(registry_rows):
    for row in registry_rows:
        p = translate_vehicle_record(row)
        he = localize_vehicle(p, "he")
        assert HEBREW.search(he.make) and he.make in p.make_raw.replace('"', "").replace("  ", " ")
        assert he.ownership == row["baalut"] or p.ownership == row["baalut"]
        assert (he.color or "") == " ".join(str(row.get("tzeva_rechev") or "").split())
        assert he.model == p.model and localize_vehicle(p, "en") == p


# ---------------------------------------------------------------- chat
def test_chat_catalogues_have_the_same_entries_and_placeholders():
    en, he = CHAT["en"], CHAT["he"]
    assert en.keys() == he.keys()
    for k, v in en.items():
        if isinstance(v, dict):
            assert v.keys() == he[k].keys()
        else:
            assert sorted(re.findall(r"\{(\w+)", v)) == sorted(re.findall(r"\{(\w+)", he[k])), k


@pytest.mark.parametrize("message", ["squeaking noise when braking", "נשמעת חריקה בבלמים"])
def test_chat_falls_back_in_the_selected_language_with_the_same_facts(profiles, models, monkeypatch, message):
    monkeypatch.setattr(settings, "openai_api_key", None)
    p = predict(profiles[4908732], models)
    en, he = (asyncio.run(chat.answer(p, message, None, TODAY, lang)) for lang in ("en", "he"))
    assert "qualified mechanic" in en["answer"] and not HEBREW.search(en["answer"])
    assert "מכונאי מוסמך" in he["answer"] and "בלמים" in he["answer"] and "OPENAI_API_KEY" in he["note"] and HEBREW.search(he["note"])
    numbers = lambda s: sorted(re.findall(r"\d[\d,]*", s))
    assert numbers(en["answer"]) == numbers(he["answer"])
    shown = localize_prediction(p, "he")
    facts_en, facts_he = chat.facts(p, TODAY), chat.facts(shown, TODAY, "he")
    assert len(facts_en) == len(facts_he) and all(HEBREW.search(f) for f in facts_he)


def test_language_model_gets_the_same_facts_and_only_another_reply_language(profiles, models, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    prompts = {}
    p = predict(profiles[4908732], models)
    for lang in ("en", "he"):
        def handler(request, lang=lang):
            prompts[lang] = json.loads(request.content)["messages"][0]["content"]
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        assert asyncio.run(chat.answer(p, "brakes", httpx.MockTransport(handler), TODAY, lang))["source"] == "openai"
    assert "Answer in Hebrew" in prompts["he"] and "Answer in English" in prompts["en"]
    assert prompts["he"].replace("Answer in Hebrew", "") == prompts["en"].replace("Answer in English", "")


# ---------------------------------------------------------------- API
def test_api_language_parameter(profiles, models, monkeypatch):
    from app.api.v1 import predict as predict_api, vehicles as vehicles_api
    from app.database import get_db
    from app.main import app

    async def profile(plate):
        return profiles.get(int(plate))

    async def no_recalls(plate):
        return RecallInfo(available=True)

    async def no_db():
        yield None

    for module in (predict_api, vehicles_api):
        monkeypatch.setattr(module, "get_vehicle_profile", profile)
    monkeypatch.setattr(predict_api, "get_recalls", no_recalls)
    app.dependency_overrides[get_db] = no_db
    try:
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                return [await c.get(u) for u in ("/api/v1/predict/4908732", "/api/v1/predict/4908732?lang=en", "/api/v1/predict/4908732?lang=he", "/api/v1/predict/4908732?lang=fr", "/api/v1/vehicles/4908732?lang=he")]

        default, en, he, bad, vehicle = asyncio.run(run())
    finally:
        app.dependency_overrides.clear()
    assert default.json() == en.json() and en.json()["vehicle"]["make"] == "Toyota"          # English stays the default
    assert he.json()["vehicle"]["make"] == "טויוטה" == vehicle.json()["make"] and bad.status_code == 422
    for k in ("level", "inputs", "observed_rate_by_level"):
        assert he.json()["failure_risk"][k] == en.json()["failure_risk"][k]
