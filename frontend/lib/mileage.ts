// Validation of the mileage typed by the user (option "I know my car's mileage"). The server validates again: this only gives an immediate, clear message.
export const MIN_MILEAGE_KM = 1;
export const MAX_MILEAGE_KM = 1_000_000;

/** The message shown is mileage.errors.<code> in messages/. */
export type MileageErrorCode = "empty" | "negative" | "digits" | "tooHigh" | "tooLow";
export type MileageParse = { ok: true; km: number } | { ok: false; code: MileageErrorCode };

export function parseMileage(raw: string): MileageParse {
  const text = raw.trim();
  if (!text) return { ok: false, code: "empty" };
  if (/^[-−]/.test(text)) return { ok: false, code: "negative" };
  const compact = text.replace(/[\s,]/g, "");
  if (!/^\d+$/.test(compact)) return { ok: false, code: "digits" };
  if (compact.length > 9) return { ok: false, code: "tooHigh" };
  const km = Number(compact);
  if (km < MIN_MILEAGE_KM) return { ok: false, code: "tooLow" };
  if (km > MAX_MILEAGE_KM) return { ok: false, code: "tooHigh" };
  return { ok: true, km };
}

export type MileageMode = "estimate" | "reported";
