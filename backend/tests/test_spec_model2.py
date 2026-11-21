"""Model 2 as Smart_Car_Models.pdf specifies (Kaggle Datasets 1 + 4; Dataset 5 for electric / hybrid vehicles), on the exported artifacts."""
import json
from pathlib import Path

import pytest

from app.ml.spec_features import M2_EV_NUMERIC, M2_FEATURES
from app.ml.spec_risk import SpecRiskInputs

ART = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts" / "spec"
CARD = json.loads((ART / "model2_card.json").read_text(encoding="utf-8"))


def x(**kw) -> SpecRiskInputs:
    base = dict(vehicle_age=9, km=150_000.0, km_source="estimated", fuel="petrol", make="Toyota")
    return SpecRiskInputs(**{**base, **kw})


def test_the_card_records_the_specified_experiments():
    for part in ("ice", "ev"):
        assert CARD[part]["chosen"] in ("XGBoost + SMOTE", "XGBoost + scale_pos_weight")           # imbalance experiment, XGBoost preferred
        assert len(CARD[part]["levels"]["cut_probabilities"]) == 2
    assert CARD["features_ice"] == M2_FEATURES and CARD["features_ev"] == M2_EV_NUMERIC
    sensors = {"Engine_Temperature", "Tire_Pressure", "Vibration_Levels", "Oil_Quality", "Battery_Status", "Brake_Condition", "Anomalies_Detected", "battery_voltage", "engine_temperature"}
    assert not sensors & set(CARD["features_ice"] + CARD["features_ev"])                          # strict feature dropping
    assert {"vehicle_age", "days_since_last_maintenance", "brand_reliability_index", "km"} <= set(CARD["features_ice"])
    assert any(k.startswith("d4_") for k in CARD["features_ice"])                                    # Dataset 4 aggregation enriches Dataset 1
    assert "kagglehub" in json.dumps(CARD["kaggle_sources"])


def test_branching_electric_and_hybrid_use_the_dataset5_model(models):
    m = models.failure_risk
    assert m.predict(x(fuel="petrol")).branch == "ice" and m.predict(x(fuel="diesel")).branch == "ice"
    assert m.predict(x(fuel="electric")).branch == "ev" and m.predict(x(fuel="hybrid")).branch == "ev"


def test_output_is_a_level_and_unknown_inputs_are_declared(models):
    r = models.failure_risk.predict(x())
    assert r.level in ("low", "moderate", "high") and 0 <= r.probability <= 1
    assert "days since the last maintenance" in r.assumed and "type of the last maintenance" in r.assumed
    known = models.failure_risk.predict(x(days_since_last_maintenance=120.0, maintenance_type="Oil"))
    assert "days since the last maintenance" not in known.assumed


def test_failure_history_raises_the_score_as_in_dataset1(models):
    m = models.failure_risk
    assert m.predict(x(failure_history=2)).probability > m.predict(x(failure_history=0)).probability


@pytest.mark.parametrize("make,expected", [("Toyota", True), ("UnknownBrand", False)])
def test_brand_reliability_index_comes_from_real_inspection_data(models, make, expected):
    idx = models.failure_risk.brand_index(make)
    assert 0 <= idx <= 100
    assert (make.lower() in CARD["brand_reliability_index"]["index"]) is expected
    if not expected:
        assert idx == CARD["brand_reliability_index"]["default"] == 50.0


def test_external_check_on_real_inspections_is_recorded():
    ext = CARD["external_check_uk_mot"]
    assert 0.4 < ext["spec_model2_auc"] < 1 and 0.4 < ext["age_only_auc"] < 1 and ext["pairs"] >= 100_000
