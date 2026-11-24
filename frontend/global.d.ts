import type en from "./messages/en.json";
import type { Locale } from "./i18n/config";

// Every key used in a component is checked by the compiler against messages/en.json.
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof en;
  }
}
