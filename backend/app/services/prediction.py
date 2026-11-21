"""Orchestrates the whole pipeline for one plate (UC-01, UC-02): registry -> Stage 1 -> Stage 2 -> rules -> recalls.

Three kinds of statements are produced and kept apart in the response:
  * inspection_risk      - a learned estimate of the risk that the NEXT annual inspection finds a defect (Model 2);
  * maintenance          - generic recommended service intervals applied to the vehicle's own records (rules, not learned);
  * recalls              - official open recalls for the plate (facts published by the Ministry of Transport).
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.registry import Models
from app.models import InspectionRecord, MaintenanceRecord, Vehicle
from app.redis_client import get_cached, set_cached
from app.schemas.prediction import (
    FailureRisk,
    HistoryInfo,
    ModelComparisonRow,
    InspectionRisk,
    MaintenanceInfo,
    MileageInfo,
    ObservedRates,
    PredictionResponse,
    Provenance,
    RecallInfo,
    RecallItem,
    RiskScale,
    RuleStatus,
    SystemRiskOut,
)
from app.schemas.vehicle import VehicleProfile
from app.ml.spec_features import CATEGORY_TO_MAINTENANCE_TYPE
from app.ml.spec_risk import SpecRiskInputs
from app.services import features, maintenance_rules, recalls, vehicle_specs

# A user-reported mileage that implies more than this many km per year of vehicle age is shown but NOT given to the risk model (a typing mistake is far more likely).
MAX_PLAUSIBLE_REPORTED_ANNUAL_KM = 60_000

SYSTEM_TITLES = {
    "brakes": "Brakes",
    "electrical": "Electrical (mostly lighting)",
    "engine_emissions": "Engine-related (emissions, fuel, mounts)",
}
RISK_DEFINITION = (
    "Relative risk that the next annual inspection finds a defect in this system, compared with reference vehicles from UK inspection data. "
    "It is not a prediction of a breakdown and it has not been validated on Israeli vehicles."
)
RISK_DISCLAIMER = (
    "These indicators are positions in a ranking, not probabilities of failure. The model was trained on UK inspections and checked on Dutch inspections; "
    "no Israeli inspection results are available, so the levels show relative risk against the reference data only."
)
FAILURE_DEFINITION = (
    "Model 2 as specified in Smart_Car_Models.pdf: an estimate of how likely the vehicle is to need maintenance for a mechanical failure, from its age, "
    "mileage, maintenance history and brand, learned from Kaggle Dataset 1 (Dataset 5 for electric and hybrid vehicles)."
)
FAILURE_DISCLAIMER = (
    "The labels of the training datasets are synthetic (generated, not observed on real vehicles) and the model has not been validated on Israeli vehicles. "
    "The level is a position among the training vehicles, not a probability; checked on real UK inspection outcomes it ranks vehicles only modestly."
)
LEVEL_TEXT = {"low": "Low", "moderate": "Moderate", "high": "High"}
SAME_AGE_TEXT = {"lower": "lower than most", "typical": "about typical for", "higher": "higher than most"}


def comparison_rows(models: Models) -> list[ModelComparisonRow]:
    """ROC-AUC of each model on its own test data, for the comparison table of the dashboard (numbers read from the model cards)."""
    card = models.failure_risk.card
    ext = card.get("external_check_uk_mot", {})
    rows = [
        ModelComparisonRow(model="Model 2 (PDF), combustion", data="Kaggle Dataset 1 (synthetic labels)", test="held-out 20% of Dataset 1", roc_auc=round(card["ice"]["test"]["roc_auc"], 3)),
        ModelComparisonRow(model="Model 2 (PDF), electric / hybrid", data="Kaggle Dataset 5 (synthetic labels)", test="held-out 20% of Dataset 5", roc_auc=round(card["ev"]["test"]["roc_auc"], 3)),
    ]
    if ext:
        rows += [ModelComparisonRow(model="Model 2 (PDF), combustion", data="real UK MOT inspections", test="defect at the next inspection", roc_auc=round(ext["spec_model2_auc"], 3)),
                 ModelComparisonRow(model="Age only (baseline)", data="real UK MOT inspections", test="defect at the next inspection", roc_auc=round(ext["age_only_auc"], 3))]
    perf = {(r["variant"], r["system"]): r for r in models.risk.reference.get("interval_standardisation_check", [])}
    for system, title in SYSTEM_TITLES.items():
        r = perf.get(("cold", system))
        if r:
            rows.append(ModelComparisonRow(model=f"Comparison model (UK inspections), {title.split(' (')[0].lower()}", data="real UK MOT inspections",
                                           test="out of sample, defect at the next inspection", roc_auc=round(r["UK cross-fitted AUC, standardised 12 months"], 3)))
    return rows


def round_to_5(x: float) -> int:
    return int(min(max(5 * round(x / 5), 5), 95))


def whole_percent(rate: float) -> float:
    return float(max(1, round(rate * 100)))


async def load_history(session: AsyncSession | None, plate: str) -> tuple[list[dict], list[dict], Vehicle | None, str | None]:
    """(inspections, maintenance records, vehicle row, error) from PostgreSQL; a database problem never breaks the prediction."""
    if session is None:
        return [], [], None, None
    try:
        vehicle = await session.get(Vehicle, plate)
        ins = (
            await session.execute(
                select(InspectionRecord).where(InspectionRecord.license_plate == plate).order_by(InspectionRecord.inspection_date.desc())
            )
        ).scalars().all()
        mnt = (
            await session.execute(
                select(MaintenanceRecord).where(MaintenanceRecord.license_plate == plate).order_by(MaintenanceRecord.service_date.desc())
            )
        ).scalars().all()
    except SQLAlchemyError as exc:  # pragma: no cover - only when the database is down
        return [], [], None, f"history store unavailable ({type(exc).__name__})"
    inspections = [
        {
            "inspection_date": r.inspection_date,
            "odometer_km": r.odometer_km,
            "brakes": r.brakes_defect,
            "electrical": r.electrical_defect,
            "engine_emissions": r.engine_defect,
            "other": r.other_defect,
        }
        for r in ins
    ]
    maintenance = [
        {
            "service_date": r.service_date,
            "mileage_at_service": r.mileage_at_service,
            "description": r.description,
            "maintenance_category": r.maintenance_category,
        }
        for r in mnt
    ]
    return inspections, maintenance, vehicle, None


async def get_recalls(license_plate: str) -> RecallInfo:
    key = f"recalls:{license_plate}"
    try:
        cached = await get_cached(key)
        if cached is not None:
            return RecallInfo.model_validate(cached)
    except Exception:  # cache problems must not hide the answer
        pass
    try:
        items = await recalls.fetch_open_recalls(license_plate)
    except Exception as exc:
        return RecallInfo(available=False, error=f"recall service unavailable ({type(exc).__name__})")
    info = RecallInfo(available=True, count=len(items), items=[RecallItem(**i) for i in items])
    try:
        await set_cached(key, info.model_dump())
    except Exception:
        pass
    return info


def match_history(profile: VehicleProfile, inspections: list[dict], today: date) -> tuple[dict | None, str | None]:
    """The model needs the result of the LAST annual inspection (the one in the registry). A recorded inspection is used only if it is that one."""
    if not inspections:
        return None, None
    latest = inspections[0]
    registry_date = features.last_test_date(profile)
    if registry_date:
        matches = abs((latest["inspection_date"] - registry_date).days) <= 60
    else:
        matches = (today - latest["inspection_date"]).days <= 14 * 30
    if matches:
        return latest, None
    where = f" of the registry ({registry_date.isoformat()})" if registry_date else ""
    return None, f"the latest recorded inspection ({latest['inspection_date'].isoformat()}) is not the last annual test{where}: history variant not used"


async def build_prediction(
    profile: VehicleProfile,
    models: Models,
    session: AsyncSession | None,
    today: date | None = None,
    odometer_km: int | None = None,
    recalls_info: RecallInfo | None = None,
) -> PredictionResponse:
    today = today or date.today()
    inspections, maintenance, vehicle, db_error = await load_history(session, profile.license_plate)
    notes: list[str] = []
    if db_error:
        notes.append(db_error)

    # ---- odometer values, kept apart: (a) an odometer stored on a record = "measured"; (b) a value typed with this request = "user_reported" (never stored, never verified)
    age = features.vehicle_age(profile)
    matched, mismatch_note = match_history(profile, inspections, today)
    measured, measured_as_of = None, None
    candidates = []
    if matched and matched["odometer_km"]:
        candidates.append((matched["inspection_date"], matched["odometer_km"]))
    candidates += [(r["service_date"], r["mileage_at_service"]) for r in maintenance if r["mileage_at_service"]]
    if candidates:
        d, v = max(candidates, key=lambda c: c[0])
        measured, measured_as_of = v, d.isoformat()
    user_km = odometer_km
    reported_implausible = user_km is not None and age >= 1 and user_km / age > MAX_PLAUSIBLE_REPORTED_ANNUAL_KM

    # ---- Stage 1: mileage estimate (always computed; shown as a range)
    try:
        specs = await vehicle_specs.get_vehicle_specs(profile.license_plate, profile.tozeret_cd, profile.degem_cd, profile.manufacture_year)
    except Exception:  # noqa: BLE001 - official tables or cache unavailable: Model 1 imputes, and says so
        specs = vehicle_specs.VehicleSpecs()
    m1_features = features.model1_features(profile, specs.engine_cc, specs.automatic, vehicle_specs.owner_count(specs))
    est = models.mileage.estimate(m1_features, features.ownership_key(profile))
    if user_km is not None:
        label = (
            f"User-reported mileage: {user_km:,} km, typed by the user for this view; it has not been verified or officially confirmed and is not stored. "
            f"Model 1 estimate for comparison: {est.km:,} km (indicative 80% range {est.km_low:,}-{est.km_high:,})."
            + (f" An odometer of {measured:,} km recorded on {measured_as_of} is on file." if measured is not None else "")
        )
        primary, source = user_km, "user_reported"
    elif measured is not None:
        label = (
            f"Measured odometer {measured:,} km as of {measured_as_of} (from a service or inspection record). "
            f"Model 1 estimate for comparison: {est.km:,} km (indicative 80% range {est.km_low:,}-{est.km_high:,})."
        )
        primary, source = measured, "measured"
    else:
        label = (
            "An estimate for similar vehicles, calibrated with official CBS statistics. "
            "The range is indicative (about 8 in 10 similar vehicles fall inside it); it is not a measurement and has not been validated for individual Israeli vehicles."
        )
        primary, source = est.km, "estimated"
    mileage = MileageInfo(
        primary_km=primary,
        primary_source=source,
        estimated_km=est.km,
        estimated_low_km=est.km_low,
        estimated_high_km=est.km_high,
        estimated_annual_km=est.annual_km,
        measured_km=measured,
        measured_as_of=measured_as_of,
        notes=list(est.notes),
        model_raw_km=est.raw_km,
        model_inputs={"age": m1_features["age"], "fuel": m1_features["fuel"], "make_model": m1_features["make_model"], "owner_type": m1_features["owner_type"],
                      "engine_cc": m1_features["engine_cc"], "automatic": m1_features["automatic"],
                      "engine_and_transmission_source": ("official model table (data.gov.il)" if specs.engine_cc is not None and specs.automatic is not None
                                                         else "partly official, partly imputed (KNN, K=5)" if specs.engine_cc is not None or specs.automatic is not None
                                                         else "imputed (KNN, K=5)")},
        estimate_reliability=est.reliability,
        estimate_reliability_reason=est.reliability_reason,
        label=label,
    )

    # ---- Stage 2: inspection-defect risk. History only from an INSPECTION record; odometer only if it was MEASURED.
    previous, inspection_date, odo_for_model = None, None, None
    if matched:
        previous = {
            "brakes": matched["brakes"],
            "electrical": matched["electrical"],
            "engine_emissions": matched["engine_emissions"],
            "any_defect": matched["brakes"] or matched["electrical"] or matched["engine_emissions"] or matched["other"],
        }
        inspection_date = matched["inspection_date"]
        odo_for_model = matched["odometer_km"]
    # The odometer variants were trained with the odometer printed on the LAST inspection. A recorded inspection odometer is exactly that and always wins. A typed mileage is the CURRENT
    # one (it includes the driving since that inspection): it is accepted as an approximation only if plausible (docs/MILEAGE_SELECTION.md); an estimate is never given to Model 2.
    odometer_source = "recorded_inspection" if odo_for_model else None
    user_note = None
    if user_km is not None:
        if odo_for_model:
            user_note = ("Used by Model 2 as the mileage. Not used by the comparison model: it uses the odometer recorded at the last inspection instead, "
                         "which is the value it was trained on.")
        elif reported_implausible:
            user_note = (f"Not used by the risk models: {user_km:,} km would mean more than {MAX_PLAUSIBLE_REPORTED_ANNUAL_KM:,} km per year for a {age}-year-old vehicle "
                         "(Model 2 uses the Model 1 estimate instead). "
                         "Please check the number.")
        else:
            odo_for_model, odometer_source = user_km, "user_reported"
    rx = features.risk_inputs(profile, previous, odo_for_model, inspection_date)
    result = models.risk.predict(rx)
    if user_km is not None and odometer_source == "user_reported":
        if result.covered:
            user_note = ("Used by Model 2 as the mileage, and by the comparison model as the odometer at the last inspection (an approximation: it includes the driving "
                         "since then). "
                         "Its accuracy depends on what was typed; it is not verified.")
        else:
            odometer_source, user_note = None, "Used by Model 2 as the mileage. Not used by the comparison model: it does not cover this vehicle."
    mileage.user_reported_km = user_km
    mileage.user_reported_used_by_model2 = odometer_source == "user_reported" and user_km is not None
    mileage.user_reported_note = user_note
    cuts = models.risk.cuts
    systems = []
    for r in result.systems:
        higher_than = round_to_5(r.reference_percentile)
        systems.append(
            SystemRiskOut(
                system=r.system,
                title=SYSTEM_TITLES[r.system],
                level=r.level,
                higher_than_of_100=higher_than,
                same_age_label=r.same_age_label,
                same_age_years=rx.age_year,
                observed_in_reference=ObservedRates(**{k: whole_percent(v) for k, v in r.observed_rates.items()}),
                explanation=(
                    f"{LEVEL_TEXT[r.level]} relative risk: the estimate is higher than about {higher_than} of 100 reference vehicles of all ages. "
                    f"Among vehicles aged {rx.age_year} it is {SAME_AGE_TEXT[r.same_age_label]} that age group."
                ),
            )
        )
    scale = None
    if result.covered:
        a_b = {s: cuts[s] for s in cuts}
        scale = RiskScale(
            reference="UK MOT inspections (2022 to 2023), out-of-sample scores of vehicles aged 3 to 20, petrol, diesel and hybrid",
            cut_percentiles={s: list(a_b[s]) for s in a_b},
            level_rule={s: f"Low: the lowest {a_b[s][0]}% of reference vehicles; Moderate: the next {a_b[s][1] - a_b[s][0]}%; High: the top {100 - a_b[s][1]}%" for s in a_b},
            interval="Standard interval of 12 months to the next annual inspection for every vehicle",
            country_note="The same order of risk was found in Dutch inspection data, with different absolute defect rates. Israeli inspection results are not available.",
        )
    risk = InspectionRisk(
        definition=RISK_DEFINITION,
        covered=result.covered,
        reasons=result.reasons,
        variant=result.variant,
        uses_history=result.uses_history,
        uses_measured_odometer=result.uses_measured_odometer and result.covered,
        odometer_source=odometer_source if result.covered else None,
        scale=scale,
        systems=systems,
        disclaimer=RISK_DISCLAIMER,
    )

    # ---- Model 2 as Smart_Car_Models.pdf specifies (age, mileage, maintenance history, brand; Dataset 5 model for electric / hybrid vehicles)
    latest_service = maintenance[0] if maintenance else None
    failure_risk = None
    try:
        mtype = None
        if latest_service:
            key = maintenance_rules.classify_record(latest_service.get("maintenance_category"), latest_service.get("description"))
            mtype = CATEGORY_TO_MAINTENANCE_TYPE.get(key or "other")
        sx = SpecRiskInputs(
            # an implausible typed value is not given to any model: Model 2 then takes the Model 1 estimate
            vehicle_age=age, km=float(est.km if reported_implausible else primary), km_source="estimated" if reported_implausible else source,
            fuel=features.fuel_key(profile), make=profile.make,
            days_since_last_maintenance=float((today - latest_service["service_date"]).days) if latest_service else None,
            failure_history=sum(1 for i in inspections if i["brakes"] or i["electrical"] or i["engine_emissions"] or i["other"]),
            maintenance_type=mtype,
            last_service_distance=float(primary - latest_service["mileage_at_service"]) if latest_service and latest_service["mileage_at_service"] and primary >= latest_service["mileage_at_service"] else None,
        )
        fr = models.failure_risk.predict(sx)
        part = models.failure_risk.card[fr.branch]
        auc = part["test"]["roc_auc"]
        quality = None
        if auc < 0.55:
            quality = (f"This model does not separate vehicles even on its own test data (ROC-AUC {auc:.2f}; 0.5 = chance): "
                       "treat the level as carrying no information.")
        elif sx.days_since_last_maintenance is None or sx.failure_history == 0:
            missing = [t for t, cond in (("no maintenance record on file", sx.days_since_last_maintenance is None),
                                         ("no recorded inspection defect", sx.failure_history == 0)) if cond]
            quality = ("In its training data the level depends mainly on the days since the last maintenance and on past failures; age, mileage and brand "
                       f"add almost nothing. For this vehicle: {', '.join(missing)}, so the level mostly reflects typical values.")
        failure_risk = FailureRisk(
            definition=FAILURE_DEFINITION,
            branch=fr.branch,
            branch_label="combustion vehicles (Kaggle Dataset 1, enriched with the Dataset 4 failure distribution)" if fr.branch == "ice" else "electric and hybrid vehicles (Kaggle Dataset 5)",
            level=fr.level,
            level_rule="Low / Moderate / High: the lowest, middle and highest third of the training vehicles by the model's score",
            observed_rate_by_level=[whole_percent(r) if r is not None else None for r in fr.observed_rate_by_level],
            inputs=fr.inputs,
            assumed=fr.assumed,
            quality_note=quality,
            disclaimer=FAILURE_DISCLAIMER,
            comparison=comparison_rows(models),
        )
    except Exception as exc:  # noqa: BLE001 - one model failing never breaks the rest of the answer
        notes.append(f"failure-risk model unavailable ({type(exc).__name__})")

    # ---- maintenance rules (not learned)
    if user_km is not None:
        rule_odo, rule_measured, rule_basis = user_km, True, "user-reported (not verified)"
    elif measured is not None:
        rule_odo, rule_measured, rule_basis = measured, True, "measured"
    else:
        rule_odo, rule_measured, rule_basis = est.km, False, "estimated (range shown above)"
    rules = maintenance_rules.evaluate(maintenance, today, features.fuel_key(profile), age, rule_odo, rule_measured)
    maint = MaintenanceInfo(
        disclaimer=maintenance_rules.DISCLAIMER,
        odometer_used_km=rule_odo,
        odometer_basis=rule_basis,
        rules=[RuleStatus(**r) for r in rules],
    )

    rec = recalls_info if recalls_info is not None else await get_recalls(profile.license_plate)
    history = HistoryInfo(
        inspections=len(inspections),
        maintenance_records=len(maintenance),
        latest_inspection_date=inspections[0]["inspection_date"].isoformat() if inspections else None,
        history_used_by_model=previous is not None and result.covered,
        note=mismatch_note,
    )
    prov = Provenance(
        model1_version=models.mileage.card.get("version", "spec"),
        model2_version=models.failure_risk.card.get("version", "spec"),
        notes=[
            "Model 1 (Smart_Car_Models.pdf): XGBoost chosen by RMSE/MAE among Linear, Ridge, Random Forest and XGBoost on Kaggle Datasets 7, 8 and 3, calibrated to CBS Publication 1923.",
            "Model 2 (Smart_Car_Models.pdf): XGBoost on Kaggle Dataset 1 (+ Dataset 4 features; Dataset 5 for electric / hybrid); synthetic labels, not validated on real vehicles.",
            "Comparison model: XGBoost trained on UK MOT inspections, validated on Dutch RDW inspections; not validated on Israeli vehicles.",
            "Maintenance advice comes from generic rules; recalls come from the Ministry of Transport open data.",
        ]
        + notes,
    )
    return PredictionResponse(vehicle=profile, mileage=mileage, failure_risk=failure_risk, inspection_risk=risk, maintenance=maint, recalls=rec, history=history, provenance=prov)
