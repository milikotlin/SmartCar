import type { Locale } from "@/i18n/config";
import type { ChatAnswer, City, GarageResults, GarageService, GoogleDetails, InspectionRecord, MaintenanceRecord, Prediction } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** What went wrong; the text shown to the user is errors.<code> in messages/. */
export type ErrorCode = "notFound" | "invalid" | "writeKey" | "writeDisabled" | "tooMany" | "registryDown" | "conflict" | "unexpected" | "unreachable";

export class ApiError extends Error {
  constructor(
    public readonly code: ErrorCode,
    public readonly status?: number,
  ) {
    super(code);
  }
}

const CODE_OF_STATUS: Record<number, ErrorCode> = { 404: "notFound", 422: "invalid", 401: "writeKey", 403: "writeDisabled", 429: "tooMany", 503: "registryDown", 409: "conflict" };

export const errorCode = (error: unknown): ErrorCode => (error instanceof ApiError ? error.code : "unreachable");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new ApiError(CODE_OF_STATUS[response.status] ?? "unexpected", response.status);
  return response.json() as Promise<T>;
}

export function fetchPrediction(plate: string, lang: Locale, odometerKm?: number | null) {
  const odometer = odometerKm ? `&odometer_km=${Math.round(odometerKm)}` : "";
  return request<Prediction>(`/api/v1/predict/${plate}?lang=${lang}${odometer}`);
}

export const fetchMaintenance = (plate: string) => request<MaintenanceRecord[]>(`/api/v1/vehicles/${plate}/maintenance`);
export const fetchInspections = (plate: string) => request<InspectionRecord[]>(`/api/v1/vehicles/${plate}/inspections`);

export const addMaintenance = (
  plate: string,
  body: { service_date: string; mileage_at_service: number; description: string; maintenance_category: string | null; total_cost: number },
  writeKey: string,
) => request<MaintenanceRecord>(`/api/v1/vehicles/${plate}/maintenance`, { method: "POST", body: JSON.stringify(body), headers: { "X-Write-Key": writeKey } });

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
  writeKey: string,
) => request<InspectionRecord>(`/api/v1/vehicles/${plate}/inspections`, { method: "POST", body: JSON.stringify(body), headers: { "X-Write-Key": writeKey } });

export const askChat = (plate: string, message: string, lang: Locale, odometerKm?: number | null) =>
  request<ChatAnswer>(`/api/v1/chat`, {
    method: "POST",
    body: JSON.stringify({ license_plate: plate, message, odometer_km: odometerKm || null, lang }),
  });

// ---------------------------------------------------------------- garages
export interface GarageQuery {
  radiusKm: number;
  service: GarageService | "";
  limit: number;
  offset: number;
}

export const searchCities = (q: string, signal?: AbortSignal) => request<City[]>(`/api/v1/garages/cities?q=${encodeURIComponent(q)}`, { signal });

export const fetchGaragesInCity = (city: number, q: GarageQuery) =>
  request<GarageResults>(`/api/v1/garages?city=${city}&radius_km=${q.radiusKm}&limit=${q.limit}&offset=${q.offset}${q.service ? `&service=${q.service}` : ""}`);

/** The position is sent in the body, never in the address, and the server does not store it. */
export const fetchGaragesNear = (position: { lat: number; lon: number }, q: GarageQuery) =>
  request<GarageResults>(`/api/v1/garages/near`, { method: "POST", body: JSON.stringify({ ...position, radius_km: q.radiusKm, service: q.service || null, limit: q.limit, offset: q.offset }) });

export const fetchGoogleDetails = (garageId: number, lang: Locale) => request<GoogleDetails>(`/api/v1/garages/${garageId}/google?lang=${lang}`);
