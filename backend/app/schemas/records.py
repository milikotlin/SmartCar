from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

EARLIEST_DATE = date(1950, 1, 1)


def _plausible(d: date, label: str) -> date:
    if d > date.today():
        raise ValueError(f"{label} cannot be in the future")
    if d < EARLIEST_DATE:
        raise ValueError(f"{label} is implausibly old")
    return d


class MaintenanceRecordIn(BaseModel):
    service_date: date
    mileage_at_service: int = Field(ge=0, le=1_500_000)
    description: str = Field(min_length=1, max_length=2000)
    maintenance_category: str | None = Field(default=None, max_length=50)
    total_cost: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("10000000"))

    @field_validator("service_date")
    @classmethod
    def _service_date(cls, v: date) -> date:
        return _plausible(v, "service date")


class MaintenanceRecordOut(MaintenanceRecordIn):
    record_id: int


class InspectionRecordIn(BaseModel):
    """Result of an annual roadworthiness inspection, by system, as printed on the inspection report."""

    inspection_date: date
    odometer_km: int | None = Field(default=None, ge=0, le=1_500_000)
    brakes_defect: bool = False
    electrical_defect: bool = False
    engine_defect: bool = False
    other_defect: bool = False
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("inspection_date")
    @classmethod
    def _inspection_date(cls, v: date) -> date:
        return _plausible(v, "inspection date")


class InspectionRecordOut(InspectionRecordIn):
    inspection_id: int
