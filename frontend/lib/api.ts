import type { ChatAnswer, InspectionRecord, MaintenanceRecord, Prediction, VehicleProfile } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class VehicleNotFoundError extends Error {}
export class InvalidPlateError extends Error {}
export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (response.status === 404) {
    throw new VehicleNotFoundError("Vehicle not found in the Ministry of Transport registry.");
  }
  if (response.status === 422) {
    throw new InvalidPlateError("The data entered is not valid (check the plate and the numbers).");
  }
  if (response.status === 409) {
    throw new ApiError("That record already exists.");
  }
  if (!response.ok) {
    throw new ApiError("Unexpected error while contacting the backend.");
  }
  return response.json() as Promise<T>;
}

export const fetchVehicleProfile = (plate: string) => request<VehicleProfile>(`/api/v1/vehicles/${plate}`);

export function fetchPrediction(plate: string, odometerKm?: number | null) {
  const q = odometerKm ? `?odometer_km=${Math.round(odometerKm)}` : "";
  return request<Prediction>(`/api/v1/predict/${plate}${q}`);
}

export const fetchMaintenance = (plate: string) => request<MaintenanceRecord[]>(`/api/v1/vehicles/${plate}/maintenance`);
export const fetchInspections = (plate: string) => request<InspectionRecord[]>(`/api/v1/vehicles/${plate}/inspections`);

export const addMaintenance = (
  plate: string,
  body: { service_date: string; mileage_at_service: number; description: string; maintenance_category: string | null; total_cost: number },
) => request<MaintenanceRecord>(`/api/v1/vehicles/${plate}/maintenance`, { method: "POST", body: JSON.stringify(body) });

export const addInspection = (
  plate: string,
  body: {
    inspection_date: string;
    odometer_km: number | null;
    brakes_defect: boolean;
    electrical_defect: boolean;
    engine_defect: boolean;
    other_defect: boolean;
  },
) => request<InspectionRecord>(`/api/v1/vehicles/${plate}/inspections`, { method: "POST", body: JSON.stringify(body) });

export const askChat = (plate: string, message: string, odometerKm?: number | null) =>
  request<ChatAnswer>(`/api/v1/chat`, {
    method: "POST",
    body: JSON.stringify({ license_plate: plate, message, odometer_km: odometerKm || null }),
  });
