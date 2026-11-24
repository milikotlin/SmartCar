import { useTranslations } from "next-intl";
import { useFmt } from "@/lib/format";
import type { FailureRisk, RiskLevel } from "@/lib/types";
import { CardHeader, StatusPill, Tag, type RiskStatus } from "./ui/StatusPill";

const LEVEL_PILL: Record<RiskLevel, RiskStatus> = { low: "ok", moderate: "warn", high: "critical" };
const SEGMENT: Record<RiskLevel, { on: string; off: string }> = {
  low: { on: "bg-ok", off: "bg-ok-bg" },
  moderate: { on: "bg-warn", off: "bg-warn-bg" },
  high: { on: "bg-critical", off: "bg-critical-bg" },
};

export function FailureRiskPanel({ risk }: { risk: FailureRisk }) {
  const t = useTranslations();
  const fmt = useFmt();
  const num = (v: unknown, digits = 0) => (typeof v === "number" ? fmt.num(v, digits) : t("failure.notAvailable"));
  const levels: RiskLevel[] = ["low", "moderate", "high"];
  const i = risk.inputs;
  const source = String(i.km_source) as "user_reported" | "measured" | "estimated";
  const d = (k: "age" | "mileage" | "days" | "serviceKm" | "failures" | "brand") => t(`failure.drivers.${k}`);
  const drivers: [string, string][] = [
    [d("age"), t("units.yearsTight", { value: num(i.vehicle_age) })],
    [d("mileage"), `${t("units.km", { value: num(i.km) })} · ${t(`failure.kmSource.${source}`)}`],
    risk.branch === "ice" ? [d("days"), num(i.days_since_last_maintenance)] : [d("serviceKm"), num(i.last_service_distance)],
    [d("failures"), num(i.failure_history)],
    [d("brand"), num(i.brand_reliability_index, 1)],
  ];
  return (
    <article className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="failure-risk">
      <CardHeader
        eyebrow={t("failure.eyebrow")}
        title={t("failure.title")}
        right={
          <>
            <Tag tone="accent">{risk.branch === "ice" ? t("failure.ice") : t("failure.ev")}</Tag>
            <Tag>{t("failure.classifier")}</Tag>
          </>
        }
      />

      <div className="mt-5 flex flex-wrap items-center gap-5">
        <StatusPill status={LEVEL_PILL[risk.level]} size="lg">
          {t(`levelsRisk.${risk.level}`)}
        </StatusPill>
        <div className="min-w-[220px] flex-1" role="img" aria-label={t(`levelsRisk.${risk.level}`)}>
          <div className="flex h-4 gap-1.5">
            {levels.map((l) => (
              <div key={l} className={`flex-1 rounded-full ${l === risk.level ? SEGMENT[l].on : SEGMENT[l].off}`} />
            ))}
          </div>
          <div className="mt-1.5 flex text-[12px] font-semibold text-ink-faint">
            {levels.map((l) => (
              <span key={l} className={`flex-1 text-center ${l === risk.level ? "text-ink" : ""}`}>
                {t(`levels.${l}`)}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2" data-testid="failure-risk-drivers">
        {drivers.map(([k, v]) => (
          <Tag key={k}>
            <span className="text-ink-faint">{k}:</span> <span className="font-bold text-ink">{v}</span>
          </Tag>
        ))}
      </div>
    </article>
  );
}
