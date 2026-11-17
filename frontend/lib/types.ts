export interface VehicleProfile {
  license_plate: string;
  make: string;
  model: string;
  manufacture_year: number;
  fuel_type: string;
  ownership: string;
  color: string | null;
  last_test_date: string | null;
}
