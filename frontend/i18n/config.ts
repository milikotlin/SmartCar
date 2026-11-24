// Languages of the interface. Adding one = a new file in messages/ and one entry here.
export const LOCALES = ["en", "he"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "smartcar-locale"; // remembers the choice (1 year); the server reads it, so the page is already in the right language and direction when it arrives
export const DIRECTION: Record<Locale, "ltr" | "rtl"> = { en: "ltr", he: "rtl" };

export function toLocale(value: string | undefined): Locale {
  return (LOCALES as readonly string[]).includes(value ?? "") ? (value as Locale) : DEFAULT_LOCALE;
}
