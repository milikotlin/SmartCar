from datetime import date

import pytest

from app.services import features, translation


def test_every_real_row_is_translated(registry_rows):
    for row in registry_rows:
        p = translation.translate_vehicle_record(row)
        assert p.license_plate == str(row["mispar_rechev"])
        assert p.make and not any("֐" <= ch <= "׿" for ch in p.make), f"manufacturer not translated: {p.make_raw!r} -> {p.make!r}"
        assert p.fuel_type in {"Petrol", "Diesel", "Hybrid", "Electric", "LPG/CNG"}
        assert p.ownership in {"Private", "Leasing", "Company", "Rental", "Dealer"}


@pytest.mark.parametrize(
    "hebrew,english",
    [("בנזין", "Petrol"), ("דיזל", "Diesel"), ("חשמל", "Electric"), ("חשמל/בנזין", "Hybrid"), ("חשמל/דיזל", "Hybrid"), ('גפמ"', "LPG/CNG")],
)
def test_fuel_values_found_in_the_registry(hebrew, english):
    assert translation.translate_fuel(hebrew) == english


@pytest.mark.parametrize(
    "raw,english",
    [("טויוטה אנגליה", "Toyota"), ("ב מ וו ארהב\"", "BMW"), ("מרצדס בנץ גרמנ", "Mercedes-Benz"), ("בי ווי די סין", "BYD"), ("סקודה צ'כיה", "Skoda"), ("אופל פולין", "Opel")],
)
def test_manufacturer_prefixes(raw, english):
    assert translation.translate_manufacturer(raw) == english


def test_unknown_values_are_returned_as_published_not_guessed():
    assert translation.translate_manufacturer("יצרן לא מוכר") == "יצרן לא מוכר"
    assert translation.translate_fuel("משהו") == "משהו"


def test_cc_string_extraction_never_raises():
    assert translation.parse_cc("1600 CC") == 1600
    assert translation.parse_cc("1,600 CC") == 1600
    assert translation.parse_cc(None) is None
    assert translation.parse_cc("n/a") is None


def test_age_and_make_vocabulary(profiles):
    toyota = profiles[4908732]
    assert features.model_make(toyota) == "Toyota"
    assert features.model_make(profiles[6246816]) == "Bmw"                    # title case, the spelling of the training data
    assert features.model_make(profiles[4639434]) == "Opel"
    assert features.fuel_key(profiles[88328404]) == "electric"
    assert features.fuel_key(profiles[43983303]) == "hybrid"
    assert features.ownership_key(profiles[67687703]) == "leasing"


def test_registry_dates_do_not_change_the_risk_indicator(profiles, models):
    """The planned interval (licence valid until minus last test) is not an input: identical vehicles must get identical indicators."""
    base = profiles[4908732].model_copy(update={"first_registration": "2015-6", "last_test_date": "2026-04-15", "license_valid_until": "2027-04-20"})
    other = base.model_copy(update={"license_valid_until": "2027-11-13"})
    a, b = features.risk_inputs(base, None, None), features.risk_inputs(other, None, None)
    assert a == b
    ra, rb = models.risk.predict(a), models.risk.predict(b)
    assert [(s.system, s.probability, s.level) for s in ra.systems] == [(s.system, s.probability, s.level) for s in rb.systems]


def test_age_of_the_last_inspection_uses_first_registration_year(profiles):
    p = profiles[4908732].model_copy(update={"first_registration": "2015-6", "last_test_date": "2026-04-15"})
    x = features.risk_inputs(p, None, None)
    assert x.age_year == 2026 - 2015
    assert x.previous is None and x.odometer_km is None


@pytest.mark.parametrize("raw,expected", [
    ("שנהב לבן", "White (ivory)"), ("כסף מטלי", "Silver metallic"), ("אפור כהה מטלי", "Dark gray metallic"), ("תכלת מטאלי", "Light blue metallic"),
    ("שחור", "Black"), ("אדום כהה (יין)", "Dark red (wine)"), ("ירוק ים", "Sea green"), ("שן פיל", "Ivory"), ("בז מטאלי", "Beige metallic"),
])
def test_registry_colours_are_translated(raw, expected):
    from app.services.translation import translate_color

    assert translate_color(raw) == expected


def test_unknown_colour_words_are_kept_as_published_and_empty_is_none():
    from app.services.translation import translate_color

    assert translate_color("סגול אלמוני") == "סגול אלמוני"        # one unknown word: nothing is guessed
    assert translate_color("") is None and translate_color(None) is None


def test_every_colour_in_the_real_registry_rows_is_translated(registry_rows):
    import re

    from app.services.translation import translate_vehicle_record

    hebrew = re.compile(r"[\u0590-\u05FF]")
    for r in registry_rows:
        p = translate_vehicle_record(r)
        assert p.color is None or not hebrew.search(p.color), (r.get("tzeva_rechev"), p.color)


@pytest.mark.parametrize("raw,expected", [("אודי מקסיקו", "Audi"), ("דודג' קנדה", "Dodge"), ("מזארטי איטליה", "Maserati"), ("לוטוס אנגליה", "Lotus"), ("טויוטה יפן", "Toyota")])
def test_more_manufacturer_spellings(raw, expected):
    from app.services.translation import translate_manufacturer

    assert translate_manufacturer(raw) == expected
