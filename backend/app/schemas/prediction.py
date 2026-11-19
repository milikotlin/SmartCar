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


class ObservedRates(BaseModel):
    """Share of the REFERENCE vehicles (UK inspection data) of each level that had a defect found at the next inspection, in whole percent."""

    low: float
    moderate: float
    high: float


class SystemRiskOut(BaseModel):
    system: str                           # brakes | electrical | engine_emissions
    title: str
    level: str                            # low | moderate | high: position among ALL reference vehicles, any age
    higher_than_of_100: int               # "higher than about N of 100 reference vehicles" (rounded to 5: it is a rank, not a probability)
    same_age_label: str                   # lower | typical | higher: position among reference vehicles of the same age
    same_age_years: int                   # the age group the complementary label refers to
    observed_in_reference: ObservedRates  # defect rate by level in the reference data (a property of the groups, not of this vehicle)
    explanation: str


class RiskScale(BaseModel):
    reference: str
    cut_percentiles: dict[str, list[int]]   # per system: [Low/Moderate boundary, Moderate/High boundary] as percentiles of the reference vehicles
    level_rule: dict[str, str]
    interval: str
    country_note: str


class InspectionRisk(BaseModel):
    kind: str = "estimated_inspection_defect_risk"
    definition: str
    covered: bool
    reasons: list[str] = []
    variant: str | None = None
    uses_history: bool = False
    uses_measured_odometer: bool = False
    scale: RiskScale | None = None
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
