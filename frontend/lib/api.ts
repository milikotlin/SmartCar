import type { VehicleProfile } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class VehicleNotFoundError extends Error {}
export class InvalidPlateError extends Error {}

export async function fetchVehicleProfile(licensePlate: string): Promise<VehicleProfile> {
  const response = await fetch(`${API_BASE_URL}/api/v1/vehicles/${licensePlate}`);

  if (response.status === 404) {
    throw new VehicleNotFoundError("Vehicle not found in the Ministry of Transport registry.");
  }
  if (response.status === 422) {
    throw new InvalidPlateError("License plate must be 7 or 8 digits.");
  }
  if (!response.ok) {
    throw new Error("Unexpected error while fetching the vehicle profile.");
  }

  return response.json();
}
