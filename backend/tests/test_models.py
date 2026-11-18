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
    assert any("electric" in n for n in models.mileage.estimate("electric", 3, "private").notes)
    assert any("capped" in n for n in models.mileage.estimate("petrol", 80, "private").notes)
    assert any("official yearly rates" in n for n in models.mileage.estimate("petrol", 25, "private").notes)


# ------------------------------------------------------------------ Model 2
BASE = dict(age_year=9, gap_next=1.0, fuel="petrol", make="Toyota")


def test_model2_artifacts_complete_and_documented(models):
    card = models.risk.card
    assert set(card["variants"]) == {"cold", "cold_odo", "hist", "hist_odo"}
    for v in card["variants"]:
        for s in ("brakes", "electrical", "engine_emissions"):
            assert (ART / "model2" / f"{v}_{s}.json").exists()
    assert "km_estimated_by_model1" not in json.dumps(card["variants"])      # the Model 1 estimate is deliberately NOT a feature
    assert card["limitations"]


def test_model2_probabilities_are_valid_and_the_bands_are_consistent(models):
    r = models.risk.predict(RiskInputs(**BASE))
    assert r.covered and r.variant == "cold" and len(r.systems) == 3
    for s in r.systems:
        assert 0 < s.probability < 1 and s.relative_risk > 0 and 1 <= s.percentile_same_age <= 99
        assert s.band in {"lower", "typical", "higher"}


def test_model2_variant_selection(models):
    prev = {"brakes": False, "electrical": True, "engine_emissions": False, "any_defect": True}
    assert models.risk.predict(RiskInputs(**BASE)).variant == "cold"
    assert models.risk.predict(RiskInputs(**BASE, odometer_km=90_000)).variant == "cold_odo"
    assert models.risk.predict(RiskInputs(**BASE, previous=prev)).variant == "hist"
    assert models.risk.predict(RiskInputs(**BASE, previous=prev, odometer_km=90_000)).variant == "hist_odo"


def test_model2_a_previous_defect_raises_the_risk_of_that_system(models):
    none = {"brakes": False, "electrical": False, "engine_emissions": False, "any_defect": False}
    for system in ("brakes", "electrical", "engine_emissions"):
        with_defect = dict(none, **{system: True, "any_defect": True})
        a = {s.system: s.probability for s in models.risk.predict(RiskInputs(**BASE, previous=none)).systems}
        b = {s.system: s.probability for s in models.risk.predict(RiskInputs(**BASE, previous=with_defect)).systems}
        assert b[system] > a[system], system        # persistence measured in the UK and Dutch data (defect now -> defect next year)


def test_model2_risk_grows_with_age_for_every_system(models):
    young = {s.system: s.probability for s in models.risk.predict(RiskInputs(**dict(BASE, age_year=4))).systems}
    old = {s.system: s.probability for s in models.risk.predict(RiskInputs(**dict(BASE, age_year=16))).systems}
    assert all(old[s] > young[s] for s in young)


@pytest.mark.parametrize(
    "kw,fragment",
    [(dict(fuel="electric"), "fuel type"), (dict(fuel="lpg_cng"), "fuel type"), (dict(age_year=1), "outside the covered range"), (dict(age_year=35), "outside the covered range")],
)
def test_model2_declines_vehicles_outside_the_training_coverage(models, kw, fragment):
    r = models.risk.predict(RiskInputs(**dict(BASE, **kw)))
    assert not r.covered and r.systems == [] and any(fragment in x for x in r.reasons)


def test_model2_unknown_make_is_grouped_not_rejected(models):
    r = models.risk.predict(RiskInputs(**dict(BASE, make="Zeekr")))
    assert r.covered and any("outside" in n for n in r.reasons)


def test_model2_golden_predictions_match_the_offline_environment(models):
    """Probabilities computed in the training environment (ml/.venv) for fixed inputs; guards against any library or encoding mismatch in the API image."""
    golden = json.loads((Path(__file__).parent / "fixtures" / "golden_model2.json").read_text(encoding="utf-8"))
    for g in golden:
        x = RiskInputs(**g["inputs"])
        got = {s.system: s.probability for s in models.risk.predict(x).systems}
        for system, p in g["probabilities"].items():
            assert got[system] == pytest.approx(p, abs=1e-5), (g["inputs"], system)


def test_model2_card_records_foreign_validation_and_no_israeli_validation():
    card = json.loads((ART / "model2" / "model2_card.json").read_text(encoding="utf-8"))
    assert card["netherlands_external_validation"] and card["uk_test_metrics"]
    assert any("not validated on Israeli" in x for x in card["limitations"])
    auc = [r["ROC-AUC"] for r in card["uk_test_metrics"]]
    assert all(0.6 < a < 0.85 for a in auc)         # modest, honest discrimination


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
