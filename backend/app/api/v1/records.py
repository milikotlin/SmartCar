from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.ml.registry import get_models
from app.models import InspectionRecord, MaintenanceRecord, Vehicle
from app.schemas.records import InspectionRecordIn, InspectionRecordOut, MaintenanceRecordIn, MaintenanceRecordOut
from app.security import rate_limit, require_write_key
from app.services import features
from app.services.vehicle_lookup import get_vehicle_profile

router = APIRouter(prefix="/api/v1/vehicles", tags=["records"])

LICENSE_PLATE_PATTERN = r"^\d{7,8}$"

# Every write needs the workshop key (see app/security.py); the rate limit runs first so that wrong keys are throttled too.
WRITE_GUARDS = [Depends(rate_limit("write", lambda: settings.write_rate_per_minute)), Depends(require_write_key)]


async def ensure_vehicle(session: AsyncSession, plate: str, mileage_hint: int | None) -> Vehicle:
    """The vehicles table is the static profile (3NF); a row is created from the registry the first time a record is stored for the plate."""
    vehicle = await session.get(Vehicle, plate)
    if vehicle is not None:
        if mileage_hint is not None and mileage_hint > vehicle.current_mileage:
            vehicle.current_mileage = mileage_hint
        return vehicle
    profile = await get_vehicle_profile(plate)
    if profile is None:
        raise HTTPException(status_code=404, detail="Vehicle not found in Ministry of Transport registry")
    if mileage_hint is None:
        est = get_models().mileage.estimate(features.fuel_key(profile), features.vehicle_age(profile), features.ownership_key(profile))
        mileage_hint = est.km
    vehicle = Vehicle(license_plate=plate, make=profile.make[:50], model=profile.model[:50], manufacture_year=profile.manufacture_year, current_mileage=mileage_hint)
    session.add(vehicle)
    try:
        await session.flush()
    except IntegrityError:          # two first records for the same plate at the same moment: the other request created the row
        await session.rollback()
        existing = await session.get(Vehicle, plate)
        if existing is None:
            raise
        return existing
    return vehicle


def check_date_against_vehicle(vehicle: Vehicle, record_date: date, what: str) -> None:
    if record_date.year < vehicle.manufacture_year:
        raise HTTPException(status_code=422, detail=f"The {what} date ({record_date.isoformat()}) is before the vehicle's year of manufacture ({vehicle.manufacture_year}).")


async def check_quota(session: AsyncSession, model, plate: str, limit: int, what: str) -> None:
    n = (await session.execute(select(func.count()).select_from(model).where(model.license_plate == plate))).scalar_one()
    if n >= limit:
        raise HTTPException(status_code=409, detail=f"This vehicle already has the maximum number of {what} ({limit}).")


@router.get("/{license_plate}/maintenance", response_model=list[MaintenanceRecordOut])
async def list_maintenance(license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN), session: AsyncSession = Depends(get_db)):
    rows = (await session.execute(select(MaintenanceRecord).where(MaintenanceRecord.license_plate == license_plate).order_by(MaintenanceRecord.service_date.desc()))).scalars().all()
    return [MaintenanceRecordOut(record_id=r.record_id, service_date=r.service_date, mileage_at_service=r.mileage_at_service, description=r.description,
                                 maintenance_category=r.maintenance_category, total_cost=r.total_cost) for r in rows]


@router.post("/{license_plate}/maintenance", response_model=MaintenanceRecordOut, status_code=201, dependencies=WRITE_GUARDS)
async def add_maintenance(body: MaintenanceRecordIn, license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN), session: AsyncSession = Depends(get_db)):
    vehicle = await ensure_vehicle(session, license_plate, body.mileage_at_service)
    check_date_against_vehicle(vehicle, body.service_date, "service")
    await check_quota(session, MaintenanceRecord, license_plate, settings.max_maintenance_per_plate, "maintenance records")
    rec = MaintenanceRecord(license_plate=license_plate, service_date=body.service_date, mileage_at_service=body.mileage_at_service, description=body.description,
                            maintenance_category=body.maintenance_category, total_cost=body.total_cost)
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return MaintenanceRecordOut(record_id=rec.record_id, **body.model_dump())


@router.get("/{license_plate}/inspections", response_model=list[InspectionRecordOut])
async def list_inspections(license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN), session: AsyncSession = Depends(get_db)):
    rows = (await session.execute(select(InspectionRecord).where(InspectionRecord.license_plate == license_plate).order_by(InspectionRecord.inspection_date.desc()))).scalars().all()
    return [InspectionRecordOut(inspection_id=r.inspection_id, inspection_date=r.inspection_date, odometer_km=r.odometer_km, brakes_defect=r.brakes_defect,
                                electrical_defect=r.electrical_defect, engine_defect=r.engine_defect, other_defect=r.other_defect, notes=r.notes) for r in rows]


@router.post("/{license_plate}/inspections", response_model=InspectionRecordOut, status_code=201, dependencies=WRITE_GUARDS)
async def add_inspection(body: InspectionRecordIn, license_plate: str = Path(..., pattern=LICENSE_PLATE_PATTERN), session: AsyncSession = Depends(get_db)):
    vehicle = await ensure_vehicle(session, license_plate, body.odometer_km)
    check_date_against_vehicle(vehicle, body.inspection_date, "inspection")
    await check_quota(session, InspectionRecord, license_plate, settings.max_inspections_per_plate, "inspection results")
    rec = InspectionRecord(license_plate=license_plate, inspection_date=body.inspection_date, odometer_km=body.odometer_km, brakes_defect=body.brakes_defect,
                           electrical_defect=body.electrical_defect, engine_defect=body.engine_defect, other_defect=body.other_defect, notes=body.notes)
    session.add(rec)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="An inspection result for this plate and date already exists")
    await session.refresh(rec)
    return InspectionRecordOut(inspection_id=rec.inspection_id, **body.model_dump())
