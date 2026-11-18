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
}

export interface MileageInfo {
  primary_km: number;
  primary_source: "measured" | "estimated";
  estimated_km: number;
  estimated_low_km: number;
  estimated_high_km: number;
  estimated_annual_km: number;
  measured_km: number | null;
  measured_as_of: string | null;
  notes: string[];
  label: string;
}

export type RiskBand = "lower" | "typical" | "higher";

export interface SystemRisk {
  system: "brakes" | "electrical" | "engine_emissions";
  title: string;
  band: RiskBand;
  percentile_same_age: number;
  relative_risk: number;
  foreign_probability: number;
  explanation: string;
}

export interface InspectionRisk {
  kind: "estimated_inspection_defect_risk";
  definition: string;
  covered: boolean;
  reasons: string[];
  variant: "cold" | "cold_odo" | "hist" | "hist_odo" | null;
  uses_history: boolean;
  uses_measured_odometer: boolean;
  systems: SystemRisk[];
  disclaimer: string;
}

export interface RuleStatus {
  key: string;
  label: string;
  interval: string;
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

export interface Prediction {
  vehicle: VehicleProfile;
  mileage: MileageInfo;
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

export interface ChatAnswer {
  answer: string;
  source: "openai" | "deterministic_fallback";
  model: string | null;
  note: string | null;
  context: string[];
}
