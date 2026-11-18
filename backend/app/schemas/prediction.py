from pydantic import BaseModel

from app.schemas.vehicle import VehicleProfile


class MileageInfo(BaseModel):
    primary_km: int                       # the figure to show: measured when known, else the Model 1 estimate
    primary_source: str                   # "measured" | "estimated"
    estimated_km: int
    estimated_low_km: int
    estimated_high_km: int
    estimated_annual_km: int
    measured_km: int | None = None
    measured_as_of: str | None = None
    notes: list[str] = []
    label: str


class SystemRiskOut(BaseModel):
    system: str                           # brakes | electrical | engine_emissions
    title: str
    band: str                             # lower | typical | higher (versus vehicles of the same age)
    percentile_same_age: int
    relative_risk: float
    foreign_probability: float            # UK-calibrated probability; NOT validated for Israel
    explanation: str


class InspectionRisk(BaseModel):
    kind: str = "estimated_inspection_defect_risk"
    definition: str
    covered: bool
    reasons: list[str] = []
    variant: str | None = None
    uses_history: bool = False
    uses_measured_odometer: bool = False
    systems: list[SystemRiskOut] = []
    disclaimer: str


class RuleStatus(BaseModel):
    key: str
    label: str
    interval: str
    advice: str
    status: str                           # ok | due_soon | overdue | no_record | no_record_overdue
    attention: bool
    last_service_date: str | None = None
    last_service_km: int | None = None
    months_since: float | None = None
    km_since: int | None = None
    basis: str | None = None
    source: str = "maintenance_rule"


class MaintenanceInfo(BaseModel):
    kind: str = "recommended_maintenance"
    disclaimer: str
    odometer_used_km: int | None = None
    odometer_basis: str
    rules: list[RuleStatus]


class RecallItem(BaseModel):
    recall_id: int | None = None
    type: str | None = None
    category: str | None = None
    related_system: str | None = None
    description_he: str | None = None
    opened: str | None = None


class RecallInfo(BaseModel):
    kind: str = "official_recall"
    source: str = "Israel Ministry of Transport open data: vehicles with open recalls"
    available: bool
    count: int = 0
    items: list[RecallItem] = []
    error: str | None = None


class HistoryInfo(BaseModel):
    inspections: int
    maintenance_records: int
    latest_inspection_date: str | None = None
    history_used_by_model: bool
    note: str | None = None


class Provenance(BaseModel):
    model1_version: str
    model2_version: str
    notes: list[str]


class PredictionResponse(BaseModel):
    vehicle: VehicleProfile
    mileage: MileageInfo
    inspection_risk: InspectionRisk
    maintenance: MaintenanceInfo
    recalls: RecallInfo
    history: HistoryInfo
    provenance: Provenance
