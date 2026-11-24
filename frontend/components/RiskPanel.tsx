import { useTranslations } from "next-intl";
import type { InspectionRisk } from "@/lib/types";
import { RiskLevelBar } from "./RiskLevelBar";
import { CardHeader, StatusPill, Tag } from "./ui/StatusPill";

/** Backend coverage codes -> 2-3 word chips. */
const REASON_CHIP = { not_covered_fuel: "fuel", not_covered_young: "young", not_covered_old: "old" } as const;
const reasonChip = (code: string | null) => (code && code in REASON_CHIP ? REASON_CHIP[code as keyof typeof REASON_CHIP] : ("other" as const));

export function RiskPanel({ risk }: { risk: InspectionRisk }) {
  const t = useTranslations("subsystem");
  return (
    <article className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="comparison-risk">
      <CardHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        right={
          risk.covered ? (
            <>
              <Tag tone="accent">{t(`variant.${risk.variant ?? "cold"}`)}</Tag>
              {risk.odometer_source === "user_reported" && <Tag>{t("odometerReported")}</Tag>}
              <Tag>{t("models")}</Tag>
            </>
          ) : undefined
        }
      />

      {risk.covered && risk.scale ? (
        <div className="mt-5 grid grid-cols-3 gap-3 max-[900px]:grid-cols-1">
          {risk.systems.map((s) => (
            <RiskLevelBar
              key={s.system}
              system={s.system}
              title={s.title}
              level={s.level}
              higherThan={s.higher_than_of_100}
              cuts={risk.scale!.cut_percentiles[s.system]}
              sameAgeLabel={s.same_age_label}
              sameAgeYears={s.same_age_years}
            />
          ))}
        </div>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-line-strong bg-paper px-4 py-4" data-testid="comparison-not-covered">
          <StatusPill status="neutral" size="md">
            {t("notCovered")}
          </StatusPill>
          <span className="text-[14px] font-semibold text-ink">{t("noEstimate")}</span>
          {risk.reasons.map((r, i) => (
            <Tag key={r} title={r}>
              {t(`reason.${reasonChip(risk.reason_codes[i] ?? null)}`)}
            </Tag>
          ))}
        </div>
      )}
    </article>
  );
}
