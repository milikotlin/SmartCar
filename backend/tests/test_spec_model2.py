"""Model 2 as Smart_Car_Models.pdf specifies (Kaggle Datasets 1 + 4; Dataset 5 branch for electric / hybrid vehicles), on the exported artifacts."""
import json
from pathlib import Path

import pytest

from app.ml.spec_features import M2_EV_FEATURES, M2_FEATURES
from app.ml.spec_risk import SpecRiskInputs

ART = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts" / "spec"
CARD = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))


def x(**kw) -> SpecRiskInputs:
    base = dict(vehicle_age=9, km=100_000.0, km_source="estimated", fuel="petrol", make="Toyota")
    return SpecRiskInputs(**{**base, **kw})


def test_the_card_records_the_specified_experiments():
    for part in ("ice", "ev"):
        assert CARD[part]["chosen"] in ("XGBoost + SMOTE", "XGBoost + scale_pos_weight", "Logistic Regression (balanced)", "Logistic Regression + SMOTE")
        assert len(CARD[part]["levels"]["cut_probabilities"]) == 2 and CARD[part]["synthetic_rows"] > 0 and 0 < CARD[part]["kaggle_share"] <= 0.4
    assert CARD["ice"]["chosen"].startswith("XGBoost")
    assert CARD["features_ice"] == M2_FEATURES and CARD["features_ev"] == M2_EV_FEATURES
    sensors = {"Engine_Temperature", "Tire_Pressure", "Vibration_Levels", "Oil_Quality", "Battery_Status", "Brake_Condition", "Anomalies_Detected", "battery_voltage", "engine_temperature"}
    assert not sensors & set(CARD["features_ice"] + CARD["features_ev"])                          # strict feature dropping
    assert {"vehicle_age", "days_since_last_maintenance", "brand_reliability_index", "km"} <= set(CARD["features_ice"])
    assert any(k.startswith("d4_") for k in CARD["features_ice"])                                    # Dataset 4 aggregation enriches Dataset 1
    assert "last_service_distance" in CARD["features_ev"]                                            # Dataset 5 columns in the electric / hybrid branch
    assert "kagglehub" in json.dumps(CARD["kaggle_sources"])


def test_no_leaking_column_is_a_feature():
    assert not {"maintenance_type", "Maintenance_Type", "Maintenance_Cost", "Predictive_Score"} & set(CARD["features_ice"] + CARD["features_ev"])
    assert "Maintenance_Type" in CARD["leakage_removed"]


def test_performance_on_real_vehicles_is_better_than_before_and_realistic():
    for part in ("ice", "ev"):
        new, old = CARD[part]["test"], CARD[part]["previous_on_same_test"]
        assert new["roc_auc"] > old["roc_auc"] + 0.05 and new["recall"] > old["recall"] and new["precision"] > old["precision"]
        assert new["precision"] > new["base_rate"] and new["roc_auc"] < 0.95                          # useful, not artificially perfect
        rates = CARD[part]["levels"]["test_rate_by_level"]
        assert rates[0] < rates[1] < rates[2]                                                         # the levels are real: more defects on the road at every step
    ice = CARD["ice"]
    assert ice["by_scenario"]["no records (plate only)"]["roc_auc"] > ice["age_only_auc"]
    assert ice["netherlands"]["no records (plate only)"]["roc_auc"] > 0.6                             # second country
    assert ice["mean_calibration_error"] < 0.03


def test_branching_electric_and_hybrid_use_the_dataset5_model(models):
    m = models.failure_risk
    assert m.predict(x(fuel="petrol")).branch == "ice" and m.predict(x(fuel="diesel")).branch == "ice"
    assert m.predict(x(fuel="electric")).branch == "ev" and m.predict(x(fuel="hybrid")).branch == "ev"


def test_output_is_a_level_and_unknown_inputs_are_declared(models):
    r = models.failure_risk.predict(x())
    assert r.level in ("low", "moderate", "high") and 0 <= r.probability <= 1 and r.scenario == "no records (plate only)"
    assert "days since the last maintenance" in r.assumed and "result of the last inspection" in r.assumed and any("odometer" in a for a in r.assumed)
    known = models.failure_risk.predict(x(days_since_last_maintenance=120.0, failure_history=0, km_source="measured"))
    assert known.assumed == [] and known.scenario == "odometer + last inspection"
    assert not models.failure_risk.predict(x(vehicle_age=1)).in_data_range and models.failure_risk.predict(x(vehicle_age=9)).in_data_range


def test_unknown_is_not_zero(models):
    m = models.failure_risk
    unknown, clean, defect = (m.predict(x(failure_history=h)).probability for h in (None, 0, 1))
    assert clean < unknown < defect                                                                  # "no inspection on file" lies between a clean one and one with a defect


@pytest.mark.parametrize("fuel", ["petrol", "hybrid"])
def test_the_direction_of_every_main_input_is_sensible(models, fuel):
    m = models.failure_risk
    p = lambda **kw: m.predict(x(fuel=fuel, **kw)).probability
    assert p(vehicle_age=4) < p(vehicle_age=9) < p(vehicle_age=15)
    assert p(km=40_000.0) < p(km=200_000.0)
    assert p(failure_history=0) < p(failure_history=1) <= p(failure_history=2)
    assert p(days_since_last_maintenance=30.0) <= p(days_since_last_maintenance=300.0)
    best = max(CARD["brand_reliability_index"]["index"], key=CARD["brand_reliability_index"]["index"].get)
    worst = min(CARD["brand_reliability_index"]["index"], key=CARD["brand_reliability_index"]["index"].get)
    assert p(make=best) <= p(make=worst)


@pytest.mark.parametrize("fuel", ["petrol", "hybrid"])
def test_a_new_car_is_never_riskier_than_an_older_one(models, fuel):
    """More age or more kilometres never lowers the score (Dataset 4 rates are non-decreasing and constrained): a brand-new car cannot be rated above a 3-year-old one."""
    m = models.failure_risk
    score = lambda age, km: m.predict(x(fuel=fuel, vehicle_age=age, km=km)).probability
    for lo, hi in (((0, 8_000.0), (3, 30_000.0)), ((1, 15_000.0), (4, 45_000.0)), ((3, 30_000.0), (8, 90_000.0))):
        assert score(*lo) <= score(*hi) + 1e-9
    kms = [5_000.0, 10_000.0, 19_000.0, 21_000.0, 45_000.0, 51_000.0, 99_000.0, 101_000.0, 160_000.0, 220_000.0]
    for age in (1, 5, 10):
        p = [score(age, k) for k in kms]
        assert all(a <= b + 1e-9 for a, b in zip(p, p[1:])), (age, p)
    assert m.predict(x(fuel=fuel, vehicle_age=0, km=8_000.0)).level == "low"


@pytest.mark.parametrize("make,expected", [("Toyota", True), ("UnknownBrand", False)])
def test_brand_reliability_index_comes_from_real_inspection_data(models, make, expected):
    idx = models.failure_risk.brand_index(make)
    assert 0 <= idx <= 100
    assert (make.lower() in CARD["brand_reliability_index"]["index"]) is expected
    if not expected:
        assert idx == CARD["brand_reliability_index"]["default"] == 50.0
