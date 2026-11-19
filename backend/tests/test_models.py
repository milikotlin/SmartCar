"""Model 1 and Model 2 behaviour on the exported artifacts (offline-trained, loaded as the API loads them)."""
import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.risk import RiskInputs

ART = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"


# ------------------------------------------------------------------ Model 1
def test_model1_reproduces_the_reference_points_of_the_offline_training(models):
    card = json.loads((ART / "model1" / "model1_card.json").read_text(encoding="utf-8"))
    for ref in card["reference_points"]:
        est = models.mileage.estimate(ref["fuel"], ref["age"], ref["ownership"])
        assert abs(est.km - ref["calibrated_km"]) <= 100, ref        # same numbers as the offline training script (rounded to 100 km)


def test_model1_is_monotone_in_age_and_the_range_brackets_the_estimate(models):
    for fuel in ("petrol", "diesel", "hybrid", "lpg_cng"):
        prev = -1
        for age in range(0, 40):
            e = models.mileage.estimate(fuel, age, "private")
            assert e.km >= prev
            assert e.km_low <= e.km <= e.km_high
            prev = e.km


def test_model1_ownership_matches_the_official_pattern(models):
    private = models.mileage.estimate("petrol", 6, "private").km
    leasing = models.mileage.estimate("petrol", 6, "leasing").km
    company = models.mileage.estimate("petrol", 6, "company").km
    assert leasing > 1.4 * private and company > 1.3 * private      # CBS Table 8: leasing 28.3 / company 24.4 against private 13.9 thousand km a year


def test_model1_population_level_matches_cbs_by_age_band(models):
    card = json.loads((ART / "model1" / "model1_card.json").read_text(encoding="utf-8"))
    for key, m in card["calibration"]["marginals"].items():
        if key.startswith("age:") and m["model_thousand_km_per_year"] is not None:
            assert abs(m["model_thousand_km_per_year"] / m["cbs_2022"] - 1) < 0.05, key


def test_model1_notes_unvalidated_cases(models):
    ev = models.mileage.estimate("electric", 3, "private")
    assert ev.reliability == "low" and "electric" in ev.reliability_reason and ev.km == models.mileage.estimate("petrol", 3, "private").km
    assert any("capped" in n for n in models.mileage.estimate("petrol", 80, "private").notes)
    assert any("official yearly rates" in n for n in models.mileage.estimate("petrol", 25, "private").notes)


# ------------------------------------------------------------------ Model 2
BASE = dict(age_year=9, fuel="petrol", make="Toyota")
SYSTEMS3 = ("brakes", "electrical", "engine_emissions")


def test_model2_artifacts_complete_and_documented(models):
    card = models.risk.card
    assert set(card["variants"]) == {"cold", "cold_odo", "hist", "hist_odo"}
    for v in card["variants"]:
        for s in SYSTEMS3:
            assert (ART / "model2" / f"{v}_{s}.json").exists()
    assert "km_estimated_by_model1" not in json.dumps(card["variants"])      # the Model 1 estimate is deliberately NOT a feature
    assert card["limitations"] and (ART / "model2" / "model2_reference.json").exists()


def test_model2_outputs_are_valid_and_consistent(models):
    r = models.risk.predict(RiskInputs(**BASE))
    assert r.covered and r.variant == "cold" and len(r.systems) == 3
    for s in r.systems:
        assert 0 < s.probability < 1 and 0 <= s.reference_percentile <= 100 and 0 <= s.same_age_percentile <= 100
        assert s.level in {"low", "moderate", "high"} and s.same_age_label in {"lower", "typical", "higher"}
        a, b = models.risk.cuts[s.system]
        assert s.level == ("low" if s.reference_percentile <= a else "moderate" if s.reference_percentile <= b else "high")
        assert set(s.observed_rates) == {"low", "moderate", "high"}


def test_model2_the_scale_is_the_same_for_every_age_and_follows_the_model_output(models):
    """Main indicator: percentile and level are monotone functions of the model output across ALL ages, makes and fuels (one common scale)."""
    rows = []
    for age in range(3, 21):
        for fuel in ("petrol", "diesel", "hybrid"):
            for make in ("Toyota", "Hyundai", "Nissan", "Kia", "Skoda", "Mazda"):
                for s in models.risk.predict(RiskInputs(age_year=age, fuel=fuel, make=make)).systems:
                    rows.append((s.system, s.probability, s.reference_percentile, s.level))
    order = {"low": 0, "moderate": 1, "high": 2}
    for system in SYSTEMS3:
        r = sorted((p, pct, lv) for sy, p, pct, lv in rows if sy == system)
        pcts = [x[1] for x in r]
        assert all(a <= b + 1e-9 for a, b in zip(pcts, pcts[1:])), system
        assert all(order[a[2]] <= order[b[2]] for a, b in zip(r, r[1:])), system
        assert {x[2] for x in r} == {"low", "moderate", "high"}


def test_model2_hyundai_i20_2022_against_nissan_micra_2014(models):
    """The case that motivated the new scale: the older car must not look better than the newer one just because it is compared with its own age group."""
    i20 = models.risk.predict(RiskInputs(age_year=4, fuel="petrol", make="Hyundai"))
    micra = models.risk.predict(RiskInputs(age_year=12, fuel="petrol", make="Nissan"))
    order = {"low": 0, "moderate": 1, "high": 2}
    for a, b in zip(i20.systems, micra.systems):
        assert b.probability > a.probability, a.system
        assert b.reference_percentile > a.reference_percentile, a.system
        assert order[b.level] >= order[a.level], a.system


def test_model2_variant_selection(models):
    prev = {"brakes": False, "electrical": True, "engine_emissions": False, "any_defect": True}
    assert models.risk.predict(RiskInputs(**BASE)).variant == "cold"
    assert models.risk.predict(RiskInputs(**BASE, odometer_km=90_000)).variant == "cold_odo"
    assert models.risk.predict(RiskInputs(**BASE, previous=prev)).variant == "hist"
    assert models.risk.predict(RiskInputs(**BASE, previous=prev, odometer_km=90_000)).variant == "hist_odo"


def test_model2_a_previous_defect_raises_the_risk_of_that_system(models):
    none = {"brakes": False, "electrical": False, "engine_emissions": False, "any_defect": False}
    for system in SYSTEMS3:
        with_defect = dict(none, **{system: True, "any_defect": True})
        a = {s.system: s.probability for s in models.risk.predict(RiskInputs(**BASE, previous=none)).systems}
        b = {s.system: s.probability for s in models.risk.predict(RiskInputs(**BASE, previous=with_defect)).systems}
        assert b[system] > a[system], system        # persistence measured in the UK and Dutch data (defect now -> defect next year)


def test_model2_risk_grows_with_age_for_every_system(models):
    young = {s.system: s.reference_percentile for s in models.risk.predict(RiskInputs(**dict(BASE, age_year=4))).systems}
    old = {s.system: s.reference_percentile for s in models.risk.predict(RiskInputs(**dict(BASE, age_year=16))).systems}
    assert all(old[s] > young[s] for s in young)


def test_model2_same_age_label_is_relative_to_the_age_group(models):
    """Complementary indicator: the same-age position removes most of the age effect that the overall scale keeps."""
    pcts = {}
    for age in (4, 12):
        for s in models.risk.predict(RiskInputs(age_year=age, fuel="petrol", make="Toyota")).systems:
            pcts[(age, s.system)] = (s.reference_percentile, s.same_age_percentile)
    for system in SYSTEMS3:
        young, old = pcts[(4, system)], pcts[(12, system)]
        assert old[0] > young[0]                                        # overall scale: the older car is riskier
        assert abs(old[1] - young[1]) < abs(old[0] - young[0])          # same-age scale compresses the age difference


@pytest.mark.parametrize(
    "kw,fragment",
    [(dict(fuel="electric"), "fuel type"), (dict(fuel="lpg_cng"), "fuel type"), (dict(age_year=1), "first annual inspection"), (dict(age_year=35), "more than 20 years old")],
)
def test_model2_declines_vehicles_outside_the_training_coverage(models, kw, fragment):
    r = models.risk.predict(RiskInputs(**dict(BASE, **kw)))
    assert not r.covered and r.systems == [] and any(fragment in x for x in r.reasons)


def test_model2_unknown_make_is_grouped_not_rejected(models):
    r = models.risk.predict(RiskInputs(**dict(BASE, make="Zeekr")))
    assert r.covered and any("outside" in n for n in r.reasons)


def test_model2_golden_predictions_match_the_offline_environment(models):
    """Probabilities and levels computed in the training environment (ml/.venv) for fixed inputs; guards against any library or encoding mismatch in the API image."""
    golden = json.loads((Path(__file__).parent / "fixtures" / "golden_model2.json").read_text(encoding="utf-8"))
    for g in golden:
        r = models.risk.predict(RiskInputs(**g["inputs"]))
        for s in r.systems:
            assert s.probability == pytest.approx(g["probabilities"][s.system], abs=1e-5), (g["inputs"], s.system)
            assert s.level == g["levels"][s.system], (g["inputs"], s.system)


def test_model2_card_records_foreign_validation_and_no_israeli_validation():
    card = json.loads((ART / "model2" / "model2_card.json").read_text(encoding="utf-8"))
    assert card["netherlands_external_validation"] and card["uk_test_metrics"]
    assert any("not validated on Israeli" in x for x in card["limitations"])
    auc = [r["ROC-AUC"] for r in card["uk_test_metrics"]]
    assert all(0.6 < a < 0.85 for a in auc)         # modest, honest discrimination


# ------------------------------------------------------------------ reference scale (levels and 12-month standardisation)
REF_PATH = ART / "model2" / "model2_reference.json"
REF = json.loads(REF_PATH.read_text(encoding="utf-8")) if REF_PATH.exists() else None


@pytest.mark.skipif(REF is None, reason="reference artifact missing")
def test_levels_are_grounded_in_observed_defect_rates():
    """For every variant and system, in the UK (cross-fitted) and in the independent Dutch data: observed defect rate Low < Moderate < High, each level large enough."""
    assert REF["standard_gap_years"] == 1.0 and "out-of-sample" in REF["reference_population"]
    for row in REF["level_rates"]:
        low, mod, high = row["low"]["rate"], row["moderate"]["rate"], row["high"]["rate"]
        assert low < mod < high, (row["variant"], row["system"], row["data"])
        assert row["low"]["ci95"][1] < row["high"]["ci95"][0], "Low and High must be statistically separated"
        if row["data"] == "UK cross-fitted":
            assert min(row[k]["share"] for k in ("low", "moderate", "high")) >= 0.19, (row["variant"], row["system"])
    for s, (a, b) in REF["level_cut_percentiles"].items():
        assert 0 < a < b < 100 and a >= 20 and b <= 80


@pytest.mark.skipif(REF is None, reason="reference artifact missing")
def test_standardising_the_interval_does_not_hurt_the_models():
    """Ranking quality with the interval fixed at 12 months against the realised interval (UK cross-fitted for all variants; Dutch out-of-sample)."""
    for row in REF["interval_standardisation_check"]:
        real, std = row["UK cross-fitted AUC, realised interval"], row["UK cross-fitted AUC, standardised 12 months"]
        assert std >= real - 0.01, row


def test_two_stage_inference_stays_under_500_ms(models, profiles):
    """SRS NFR: the two-stage pipeline (Stage 1 + Stage 2) must not exceed 500 ms."""
    import statistics
    import time

    from app.services import features

    prev = {"brakes": True, "electrical": False, "engine_emissions": False, "any_defect": True}
    times = []
    for profile in list(profiles.values()) * 4:
        t0 = time.perf_counter()
        est = models.mileage.estimate(features.fuel_key(profile), features.vehicle_age(profile), features.ownership_key(profile))
        models.risk.predict(features.risk_inputs(profile, prev, est.km))
        times.append(time.perf_counter() - t0)
    print(f"two-stage inference: median {statistics.median(times) * 1000:.1f} ms, max {max(times) * 1000:.1f} ms over {len(times)} runs")
    assert max(times) < 0.5


def test_model2_has_no_input_from_model1():
    """SRS 6.2 lists the Model 1 estimate as an input of Model 2. The experiments (notebooks 04, 07, 09) showed no gain, so by decision it is NOT used: this test pins the architecture."""
    from dataclasses import fields

    assert {f.name for f in fields(RiskInputs)} == {"age_year", "fuel", "make", "previous", "odometer_km"}          # odometer_km is a MEASURED value only
    card = json.loads((ART / "model2" / "model2_card.json").read_text(encoding="utf-8"))
    used = {c for cols in card["variants"].values() for c in cols}
    assert used == {"age_year", "gap_next", "fuel", "make_c", "km", "cur_brakes", "cur_electrical", "cur_engine_emissions", "cur_any_defect"}
    assert not any("estimate" in c or "model1" in c for c in used)


def test_model1_flags_low_reliability_where_the_training_data_cannot_support_the_estimate(models):
    """Hybrids older than 7 years have 2 to 5 training vehicles per year of age: the old estimate gave 35,000 to 46,000 km per year there."""
    m1 = models.mileage
    prev = m1.estimate("hybrid", 7, "private")
    assert prev.reliability == "ok"
    for age in range(8, 16):
        e, before = m1.estimate("hybrid", age, "private"), m1.estimate("hybrid", age - 1, "private")
        assert e.reliability == "low" and "hybrid" in e.reliability_reason and "older than 7" in e.reliability_reason
        assert 8_000 <= e.km - before.km <= 18_000, (age, e.km - before.km)          # the yearly growth of the petrol curve, not the 5-vehicle data
    lpg = m1.estimate("lpg_cng", 10, "private")
    assert lpg.reliability == "low" and "LPG/CNG" in lpg.reliability_reason
    for fuel in ("petrol", "diesel"):
        assert all(m1.estimate(fuel, a, "private").reliability == "ok" for a in range(1, 30))


def test_model1_flags_estimates_that_imply_more_than_the_official_statistics_publish(models):
    from app.ml.mileage import MAX_PLAUSIBLE_ANNUAL_KM

    flagged = [(f, o, a) for f in ("petrol", "diesel", "hybrid") for o in ("private", "leasing", "company", "rental") for a in range(1, 14)
               if models.mileage.estimate(f, a, o).annual_km > MAX_PLAUSIBLE_ANNUAL_KM]
    assert flagged and all(models.mileage.estimate(*x[:1], x[2], x[1]).reliability == "low" for x in flagged)
    assert all("official statistics" in models.mileage.estimate(f, a, o).reliability_reason for f, o, a in flagged if f != "hybrid" or a <= 7)
    assert models.mileage.estimate("petrol", 8, "private").reliability == "ok"
