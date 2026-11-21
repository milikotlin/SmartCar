// Validation of the mileage typed by the user (option "I know my car's mileage"). The server validates again: this only gives an immediate, clear message.
export const MIN_MILEAGE_KM = 1;
export const MAX_MILEAGE_KM = 1_000_000;

export type MileageParse = { ok: true; km: number } | { ok: false; message: string };

export function parseMileage(raw: string): MileageParse {
  const text = raw.trim();
  if (!text) return { ok: false, message: "Enter your current mileage in kilometres." };
  if (/^[-−]/.test(text)) return { ok: false, message: "Mileage cannot be negative." };
  const compact = text.replace(/[\s,]/g, "");
  if (!/^\d+$/.test(compact)) return { ok: false, message: "Use whole kilometres, digits only (for example 123456)." };
  if (compact.length > 9) return { ok: false, message: `That is higher than ${MAX_MILEAGE_KM.toLocaleString("en-US")} km. Please check the number.` };
  const km = Number(compact);
  if (km < MIN_MILEAGE_KM) return { ok: false, message: "Mileage must be at least 1 km." };
  if (km > MAX_MILEAGE_KM) return { ok: false, message: `That is higher than ${MAX_MILEAGE_KM.toLocaleString("en-US")} km. Please check the number.` };
  return { ok: true, km };
}

export type MileageMode = "estimate" | "reported";
