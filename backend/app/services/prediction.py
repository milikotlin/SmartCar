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
    HistoryInfo,
    InspectionRisk,
    MaintenanceInfo,
    MileageInfo,
    PredictionResponse,
    Provenance,
    RecallInfo,
    RecallItem,
    RuleStatus,
    SystemRiskOut,
)
from app.schemas.vehicle import VehicleProfile
from app.services import features, maintenance_rules, recalls

SYSTEM_TITLES = {
    "brakes": "Brakes",
    "electrical": "Electrical (mostly lighting)",
    "engine_emissions": "Engine-related (emissions, fuel, mounts)",
}
RISK_DEFINITION = (
    "Estimated risk that the next annual inspection finds a defect in this system, learned from UK and Dutch inspection data. "
    "It is not a prediction of a breakdown and it has not been validated on Israeli vehicles."
)
RISK_DISCLAIMER = (
    "Ranks the vehicle against vehicles of the same age. The probability is calibrated on foreign inspections and is shown for reference only; "
    "it is not a validated probability for Israel."
)
BAND_TEXT = {"higher": "Higher than similar vehicles", "typical": "Typical for its age", "lower": "Lower than similar vehicles"}


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
) -> PredictionResponse:
    today = today or date.today()
    inspections, maintenance, vehicle, db_error = await load_history(session, profile.license_plate)
    notes: list[str] = []
    if db_error:
        notes.append(db_error)

    # ---- measured odometer (never invented): request > matched inspection record > most recent service record
    matched, mismatch_note = match_history(profile, inspections, today)
    measured, measured_as_of = None, None
    if odometer_km is not None:
        measured, measured_as_of = odometer_km, today.isoformat()
    else:
        candidates = []
        if matched and matched["odometer_km"]:
            candidates.append((matched["inspection_date"], matched["odometer_km"]))
        candidates += [(r["service_date"], r["mileage_at_service"]) for r in maintenance if r["mileage_at_service"]]
        if candidates:
            d, v = max(candidates, key=lambda c: c[0])
            measured, measured_as_of = v, d.isoformat()

    # ---- Stage 1: mileage estimate (always computed; shown as a range)
    age = features.vehicle_age(profile)
    est = models.mileage.estimate(features.fuel_key(profile), age, features.ownership_key(profile))
    if measured is not None:
        label = (
            f"Measured odometer {measured:,} km as of {measured_as_of}. "
            f"Model 1 estimate for comparison: {est.km:,} km (indicative 80% range {est.km_low:,}-{est.km_high:,})."
        )
        primary, source = measured, "measured"
    else:
        label = (
            f"Estimated {est.km:,} km (indicative 80% range {est.km_low:,}-{est.km_high:,}). Population-level estimate calibrated with "
            "official CBS statistics; not a measurement and not validated for individual Israeli vehicles."
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
    if odometer_km is not None:
        odo_for_model = odometer_km  # a measured value supplied with the request is taken as the odometer at the last inspection
    rx = features.risk_inputs(profile, previous, odo_for_model, inspection_date)
    result = models.risk.predict(rx)
    systems = [
        SystemRiskOut(
            system=s.system,
            title=SYSTEM_TITLES[s.system],
            band=s.band,
            percentile_same_age=s.percentile_same_age,
            relative_risk=round(s.relative_risk, 2),
            foreign_probability=round(s.probability, 4),
            explanation=(
                f"{BAND_TEXT[s.band]}: ranked at the {s.percentile_same_age}th percentile among vehicles of the same age; "
                f"{s.relative_risk:.1f} times the average rate of that age in the training data."
            ),
        )
        for s in result.systems
    ]
    risk = InspectionRisk(
        definition=RISK_DEFINITION,
        covered=result.covered,
        reasons=result.reasons,
        variant=result.variant,
        uses_history=result.uses_history,
        uses_measured_odometer=result.uses_measured_odometer,
        systems=systems,
        disclaimer=RISK_DISCLAIMER,
    )

    # ---- maintenance rules (not learned)
    rule_odo, rule_measured = (measured, True) if measured is not None else (est.km, False)
    rules = maintenance_rules.evaluate(maintenance, today, features.fuel_key(profile), age, rule_odo, rule_measured)
    maint = MaintenanceInfo(
        disclaimer=maintenance_rules.DISCLAIMER,
        odometer_used_km=rule_odo,
        odometer_basis="measured" if rule_measured else "estimated (range shown above)",
        rules=[RuleStatus(**r) for r in rules],
    )

    rec = await get_recalls(profile.license_plate)
    history = HistoryInfo(
        inspections=len(inspections),
        maintenance_records=len(maintenance),
        latest_inspection_date=inspections[0]["inspection_date"].isoformat() if inspections else None,
        history_used_by_model=previous is not None,
        note=mismatch_note,
    )
    prov = Provenance(
        model1_version=models.mileage.card["version"],
        model2_version=models.risk.card["version"],
        notes=[
            "Model 1: XGBoost on UK, Indian and Cardekho used-car listings, calibrated to CBS Publication 1923.",
            "Model 2: XGBoost trained on UK MOT inspections, validated on Dutch RDW inspections; not validated on Israeli vehicles.",
            "Maintenance advice comes from generic rules; recalls come from the Ministry of Transport open data.",
        ]
        + notes,
    )
    return PredictionResponse(vehicle=profile, mileage=mileage, inspection_risk=risk, maintenance=maint, recalls=rec, history=history, provenance=prov)
