from pydantic import BaseModel, ConfigDict

from app.schemas.vehicle import VehicleProfile


class MileageInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    primary_km: int                       # the figure to show: measured when known, else the Model 1 estimate
    primary_source: str                   # "user_reported" (typed by the user, not verified) | "measured" (an odometer stored on a service or inspection record) | "estimated" (Model 1)
    estimated_km: int
    estimated_low_km: int
    estimated_high_km: int
    estimated_annual_km: int
    measured_km: int | None = None        # odometer stored on a service / inspection record (never the typed value)
    measured_as_of: str | None = None
    user_reported_km: int | None = None   # the value typed by the user for this request only: never stored, never verified
    user_reported_used_by_model2: bool = False
    user_reported_note: str | None = None # why it is or is not used by the risk model, and any plausibility warning
    notes: list[str] = []
    model_raw_km: int | None = None       # Model 1 (Smart_Car_Models.pdf) output before the CBS calibration
    model_inputs: dict = {}                # the features Model 1 used (engine size and transmission from the official model table, or imputed)
    estimate_reliability: str = "ok"       # ok | low: low when the training data do not support this fuel type at this age
    estimate_reliability_reason: str | None = None
    estimate_reliability_code: str | None = None   # language-independent code of the reason (app/i18n/domain.py)
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
    reason_codes: list[str | None] = []    # language-independent code of each reason
    variant: str | None = None
    uses_history: bool = False
    uses_measured_odometer: bool = False   # an odometer value (recorded or user-reported) is an input of the model
    odometer_source: str | None = None     # "recorded_inspection" | "user_reported" | None
    scale: RiskScale | None = None
    systems: list[SystemRiskOut] = []
    disclaimer: str


class RuleStatus(BaseModel):
    key: str
    label: str
    interval: str
    interval_months: int | None = None
    interval_km: int | None = None
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
    odometer_basis_code: str | None = None
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


class ModelComparisonRow(BaseModel):
    model: str
    data: str
    test: str
    roc_auc: float | None = None


class FailureRisk(BaseModel):
    """Model 2 as Smart_Car_Models.pdf specifies: a probability score for a future mechanical failure / required maintenance, shown as three levels."""

    kind: str = "estimated_failure_risk"
    definition: str
    branch: str                           # "ice" (Dataset 1, combustion) | "ev" (Dataset 5, electric / hybrid)
    branch_label: str
    level: str                            # low | moderate | high (thirds of real UK vehicles); no percentage is shown
    level_rule: str
    observed_rate_by_level: list[float | None]   # share of real UK test vehicles of each level with a defect at the next inspection, whole %
    inputs: dict = {}
    assumed: list[str] = []
    quality_note: str | None = None       # what the level is worth for THIS vehicle (test result in the same situation, age outside the data, ...)
    disclaimer: str
    comparison: list[ModelComparisonRow] = []


class PredictionResponse(BaseModel):
    vehicle: VehicleProfile
    mileage: MileageInfo
    failure_risk: FailureRisk | None = None    # Model 2 (Smart_Car_Models.pdf); None only if it could not run
    inspection_risk: InspectionRisk            # comparison model on real inspection outcomes (UK MOT / Dutch RDW)
    maintenance: MaintenanceInfo
    recalls: RecallInfo
    history: HistoryInfo
    provenance: Provenance
