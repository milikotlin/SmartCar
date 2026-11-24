export interface VehicleProfile {
  license_plate: string;
  make: string;
  model: string;
  manufacture_year: number;
  fuel_type: string;
  ownership: string;
  color: string | null;
  last_test_date: string | null;
  license_valid_until: string | null;
  first_registration: string | null;
  trim_level: string | null;
  make_raw: string | null;
  color_raw?: string | null;
}

export interface MileageInfo {
  primary_km: number;
  /** user_reported: typed by the user, not verified. measured: an odometer stored on a service/inspection record. estimated: Model 1. */
  primary_source: "user_reported" | "measured" | "estimated";
  estimated_km: number;
  estimated_low_km: number;
  estimated_high_km: number;
  estimated_annual_km: number;
  measured_km: number | null;
  measured_as_of: string | null;
  user_reported_km: number | null;
  user_reported_used_by_model2: boolean;
  user_reported_note: string | null;
  notes: string[];
  model_raw_km: number | null;
  model_inputs: Record<string, string | number | null>;
  estimate_reliability: "ok" | "low";
  estimate_reliability_reason: string | null;
  /** language-independent code of the reason (backend app/i18n/domain.py) */
  estimate_reliability_code: string | null;
  label: string;
}

export type RiskLevel = "low" | "moderate" | "high";
export type SameAgeLabel = "lower" | "typical" | "higher";

export interface SystemRisk {
  system: "brakes" | "electrical" | "engine_emissions";
  title: string;
  /** Position among ALL reference vehicles, any age. A relative level, not a probability. */
  level: RiskLevel;
  /** "Higher than about N of 100 reference vehicles" (rounded to 5). */
  higher_than_of_100: number;
  /** Position among reference vehicles of the SAME age: complementary information. */
  same_age_label: SameAgeLabel;
  same_age_years: number;
  /** Share of reference vehicles of each level that had a defect at the next inspection, whole percent (a property of the groups, not of this vehicle). */
  observed_in_reference: { low: number; moderate: number; high: number };
  explanation: string;
}

export interface RiskScale {
  reference: string;
  cut_percentiles: Record<string, [number, number]>;
  level_rule: Record<string, string>;
  interval: string;
  country_note: string;
}

export interface InspectionRisk {
  kind: "estimated_inspection_defect_risk";
  definition: string;
  covered: boolean;
  reasons: string[];
  reason_codes: (string | null)[];
  variant: "cold" | "cold_odo" | "hist" | "hist_odo" | null;
  uses_history: boolean;
  uses_measured_odometer: boolean;
  odometer_source: "recorded_inspection" | "user_reported" | null;
  scale: RiskScale | null;
  systems: SystemRisk[];
  disclaimer: string;
}

export interface RuleStatus {
  key: string;
  label: string;
  interval: string;
  interval_months: number | null;
  interval_km: number | null;
  advice: string;
  status: "ok" | "due_soon" | "overdue" | "no_record" | "no_record_overdue";
  attention: boolean;
  last_service_date: string | null;
  last_service_km: number | null;
  months_since: number | null;
  km_since: number | null;
  basis: string | null;
}

export interface MaintenanceInfo {
  kind: "recommended_maintenance";
  disclaimer: string;
  odometer_used_km: number | null;
  odometer_basis: string;
  odometer_basis_code: string | null;
  rules: RuleStatus[];
}

export interface RecallItem {
  recall_id: number | null;
  type: string | null;
  category: string | null;
  related_system: string | null;
  description_he: string | null;
  opened: string | null;
}

export interface RecallInfo {
  kind: "official_recall";
  source: string;
  available: boolean;
  count: number;
  items: RecallItem[];
  error: string | null;
}

export interface HistoryInfo {
  inspections: number;
  maintenance_records: number;
  latest_inspection_date: string | null;
  history_used_by_model: boolean;
  note: string | null;
}

export interface ModelComparisonRow {
  model: string;
  data: string;
  test: string;
  roc_auc: number | null;
}

/** Model 2 as specified in Smart_Car_Models.pdf: a probability score shown only as three levels. */
export interface FailureRisk {
  kind: "estimated_failure_risk";
  definition: string;
  branch: "ice" | "ev";
  branch_label: string;
  level: RiskLevel;
  level_rule: string;
  observed_rate_by_level: (number | null)[];
  inputs: Record<string, string | number>;
  assumed: string[];
  quality_note: string | null;
  disclaimer: string;
  comparison: ModelComparisonRow[];
}

export interface Prediction {
  vehicle: VehicleProfile;
  mileage: MileageInfo;
  failure_risk: FailureRisk | null;
  inspection_risk: InspectionRisk;
  maintenance: MaintenanceInfo;
  recalls: RecallInfo;
  history: HistoryInfo;
  provenance: { model1_version: string; model2_version: string; notes: string[] };
}

export interface MaintenanceRecord {
  record_id: number;
  service_date: string;
  mileage_at_service: number;
  description: string;
  maintenance_category: string | null;
  total_cost: string | number;
}

export interface InspectionRecord {
  inspection_id: number;
  inspection_date: string;
  odometer_km: number | null;
  brakes_defect: boolean;
  electrical_defect: boolean;
  engine_defect: boolean;
  other_defect: boolean;
  notes: string | null;
}

export const GARAGE_SERVICES = ["mechanics", "ev_hybrid", "electrical", "brakes", "tires", "suspension", "air_conditioning", "bodywork", "gearbox", "exhaust_cooling", "pre_purchase"] as const;
export type GarageService = (typeof GARAGE_SERVICES)[number];

export interface City {
  code: number;
  name_he: string;
  name_en: string;
  garages: number;
}

/** A licensed garage of the official register. Names and addresses are published in Hebrew only. */
export interface Garage {
  id: number;
  name: string;
  address: string;
  locality: string;
  city_he: string;
  city_en: string;
  phone: string;
  services: GarageService[];
  lat: number | null;
  lon: number | null;
  position: "house" | "street" | "none";
  /** straight line; null when the position is not known */
  distance_km: number | null;
  in_city: boolean | null;
  opening_hours: string | null;
  google_maps_url: string;
  waze_url: string;
  google_search_url: string;
}

export interface GarageResults {
  mode: "city" | "gps";
  city: City | null;
  centre: { lat: number; lon: number } | null;
  approximate: boolean;
  radius_km: number;
  total: number;
  total_in_city: number | null;
  without_position: number;
  offset: number;
  items: Garage[];
  ratings_available: boolean;
  source: string;
  as_of: string;
  stale: boolean;
}

export interface GoogleDetails {
  matched: boolean;
  name: string | null;
  address: string | null;
  rating: number | null;
  rating_count: number | null;
  phone: string | null;
  opening_hours: string[];
  url: string | null;
  attribution: string | null;
}

export interface ChatAnswer {
  answer: string;
  source: "openai" | "deterministic_fallback";
  model: string | null;
  note: string | null;
  context: string[];
}
