import { useFormatter, useTranslations } from "next-intl";

/** Numbers and kilometres in the language of the interface. */
export function useFmt() {
  const f = useFormatter();
  const t = useTranslations("units");
  const num = (n: number, digits = 0) => f.number(n, { maximumFractionDigits: digits });
  return { num, km: (n: number) => t("km", { value: num(n) }) };
}
