"""Model 1 (Smart_Car_Models.pdf) and the comparison model on real inspections, on the exported artifacts (loaded as the API loads them). Model 2 of the PDF: test_spec_model2.py."""
import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.risk import RiskInputs

ART = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"


# ------------------------------------------------------------------ Model 1 (Smart_Car_Models.pdf: Kaggle Datasets 7 + 8 + 3)
def m1(fuel="petrol", age=6, own="private", engine=1600, automatic=0.0, owners="Unknown", mm="toyota|corolla"):
    from app.ml.registry import get_models

    return get_models().mileage.estimate({"age": age, "engine_cc": engine, "automatic": automatic, "fuel": fuel, "owner_type": owners, "make_model": mm}, own)


def test_model1_is_the_pipeline_the_experiments_chose(models):
    card = json.loads((ART / "spec" / "model1_card.json").read_text(encoding="utf-8"))
    steps = models.mileage.pipeline.named_steps
    assert type(steps["model"]).__name__ == {"XGBoost (no scaling)": "XGBRegressor", "Random Forest (no scaling)": "RandomForestRegressor"}.get(card["chosen"]["algorithm"], "?")
    encoder = steps["prep"].named_transformers_["make_model"].named_steps["encode"]
    assert type(encoder).__name__ == ("FrequencyEncoder" if card["chosen"]["encoding"] == "frequency" else "TargetEncoder")
    imputer = steps["prep"].named_transformers_["numeric"].named_steps["impute"]
    assert type(imputer).__name__ == "VehicleKNNImputer" and imputer.imputer_.n_neighbors == 5                                   # KNN imputer, K=5
    scores = card["algorithm_experiment"]["scores"]
    assert min(scores, key=lambda k: scores[k]["score"]) == card["chosen"]["algorithm"]                          # chosen purely by RMSE on the two REAL validation sets
    assert all({"rmse", "mae", "r2"} <= set(s[v]) for s in scores.values() for v in ("kaggle_val", "official_val"))
    assert {"Linear Regression + StandardScaler", "Ridge + StandardScaler", "Ridge + MinMaxScaler", "Random Forest (no scaling)", "XGBoost (no scaling)"} <= set(scores)
    assert set(card["encoding_experiment"]["scores"]) == {"target", "frequency"}
    assert card["rows_by_dataset"] == {"d7_uk": 93580, "d3_cardekho": 13082, "d8_in": 7196}                       # the original Kaggle rows are all there


def test_model1_augmentation_is_synthetic_faithful_and_tested_on_real_data_only(models):
    card = json.loads((ART / "spec" / "model1_card.json").read_text(encoding="utf-8"))
    assert card["synthetic_training_rows"] == 250_000
    f = card["synthetic_fidelity"]["official (against real vehicles the generator never saw)"]
    assert max(f["ks_statistic"].values()) < 0.05 and f["largest_spearman_difference"] < 0.05                     # same distributions and correlations as real vehicles
    cmp = card["comparison_with_previous_version"]
    real, kaggle = cmp["real odometers (the same 6,000 official test vehicles)"], cmp["kaggle_test (same 20% of the listings)"]
    assert real["new"]["rmse"] < 0.8 * real["previous"]["rmse"] and real["new"]["mae"] < 0.8 * real["previous"]["mae"] and real["new"]["r2"] > real["previous"]["r2"] + 0.3
    assert kaggle["new"]["rmse"] < 1.01 * kaggle["previous"]["rmse"]                                             # and the Kaggle performance is kept
    o = card["overfitting_check"]
    assert o["synthetic_train_r2"] - o["official_val_real_r2"] < 0.1 and o["kaggle_train_r2"] - o["kaggle_val_r2"] < 0.05
    assert card["test"]["official_test"]["r2"] < 0.95 and card["test"]["kaggle_test"]["r2"] < 0.95               # realistic, not artificially perfect


def test_model1_gives_model2_the_odometer_on_its_own_scale(models):
    f = {"age": 8, "engine_cc": 1600, "automatic": 1.0, "fuel": "petrol", "owner_type": "First", "make_model": "toyota|corolla"}
    est = models.mileage.estimate(f, "private")
    base = models.mileage.model2_km(f)
    assert 20_000 < base < 200_000
    assert models.mileage.model2_km(f, est.km, est.km) == pytest.approx(base)                                     # an odometer equal to the estimate changes nothing
    assert models.mileage.model2_km(f, 1.5 * est.km, est.km) == pytest.approx(1.5 * base)


def test_model1_is_monotone_in_age_and_the_range_brackets_the_estimate(models):
    for fuel in ("petrol", "diesel", "hybrid", "lpg_cng"):
        prev = -1
        for age in range(0, 40):
            e = m1(fuel, age)
            assert e.km >= prev and e.km_low <= e.km <= e.km_high, (fuel, age)
            prev = e.km


def test_model1_uses_the_features_of_the_pdf(models):
    assert m1(engine=3000).raw_km != m1(engine=1000).raw_km or m1(automatic=1.0).raw_km != m1(automatic=0.0).raw_km
    assert m1(mm="toyota|corolla").raw_km != m1(mm="bmw|x5").raw_km or m1(owners="First").raw_km != m1(owners="Fourth & Above").raw_km


def test_model1_ownership_matches_the_official_pattern(models):
    private, leasing, company = m1(own="private").km, m1(own="leasing").km, m1(own="company").km
    assert leasing > 1.4 * private and company > 1.3 * private      # CBS Table 8: leasing 28.3 / company 24.4 against private 13.9 thousand km a year


def test_model1_unknown_engine_and_transmission_are_imputed_and_said(models):
    e = m1(engine=None, automatic=None)
    assert e.km > 0 and any("KNN imputer" in n for n in e.notes)
    assert not any("KNN imputer" in n for n in m1().notes)


def test_model1_flags_low_reliability(models):
    ev = m1("electric", 3)
    assert ev.reliability == "low" and "electric" in ev.reliability_reason
    for age in range(9, 16):
        e = m1("hybrid", age)
        assert e.reliability == "low" and "hybrid" in e.reliability_reason
    assert m1("hybrid", 5).reliability == "ok" and m1("petrol", 8).reliability == "ok"
    assert any("capped" in n for n in m1(age=80).notes) and any("official yearly rates" in n for n in m1(age=28).notes)


def test_model1_shows_the_official_average_when_the_model_exaggerates(models):
    e = m1("diesel", 1, own="leasing", engine=1968, automatic=1.0, mm="skoda|superb")
    if e.reliability == "low":
        assert "official average" in e.reliability_reason and e.annual_km <= 40_000
    for fuel in ("petrol", "diesel", "hybrid"):
        for own in ("private", "leasing", "company", "rental"):
            for age in range(1, 26):
                assert m1(fuel, age, own).annual_km <= 40_000, (fuel, own, age)


def test_model1_calibration_matches_cbs(models):
    card = json.loads((ART / "spec" / "model1_card.json").read_text(encoding="utf-8"))
    assert card["calibration"]["joint_cell_mean_abs_pct_error"] < 10                                            # held-out CBS Table-8 cells
    assert 0.75 <= card["interval_80pct_heldout_coverage"] <= 0.85


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

    from app.ml.spec_risk import SpecRiskInputs
    from app.services import features

    times = []
    for profile in list(profiles.values()) * 3:
        t0 = time.perf_counter()
        est = models.mileage.estimate(features.model1_features(profile, None, None, None), features.ownership_key(profile))
        models.failure_risk.predict(SpecRiskInputs(vehicle_age=features.vehicle_age(profile), km=est.km, km_source="estimated", fuel=features.fuel_key(profile), make=profile.make))
        times.append(time.perf_counter() - t0)
    print(f"two-stage inference: median {statistics.median(times) * 1000:.1f} ms, max {max(times) * 1000:.1f} ms over {len(times)} runs")
    assert max(times) < 0.5


def test_comparison_model_has_no_input_from_model1():
    """The COMPARISON model (real UK inspections) does not use the Model 1 estimate (no gain in notebooks 04, 07, 09). Model 2 of the PDF does, as specified."""
    from dataclasses import fields

    assert {f.name for f in fields(RiskInputs)} == {"age_year", "fuel", "make", "previous", "odometer_km"}          # odometer_km is a MEASURED value only
    card = json.loads((ART / "model2" / "model2_card.json").read_text(encoding="utf-8"))
    used = {c for cols in card["variants"].values() for c in cols}
    assert used == {"age_year", "gap_next", "fuel", "make_c", "km", "cur_brakes", "cur_electrical", "cur_engine_emissions", "cur_any_defect"}
    assert not any("estimate" in c or "model1" in c for c in used)
