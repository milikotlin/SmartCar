import type { FailureRisk, RiskLevel } from "@/lib/types";
import { CardHeader, StatusPill, Tag, type RiskStatus } from "./ui/StatusPill";

const LEVEL_NAME: Record<RiskLevel, string> = { low: "Low", moderate: "Moderate", high: "High" };
const LEVEL_PILL: Record<RiskLevel, RiskStatus> = { low: "ok", moderate: "warn", high: "critical" };
const SEGMENT: Record<RiskLevel, { on: string; off: string }> = {
  low: { on: "bg-ok", off: "bg-ok-bg" },
  moderate: { on: "bg-warn", off: "bg-warn-bg" },
  high: { on: "bg-critical", off: "bg-critical-bg" },
};
const KM_SOURCE: Record<string, string> = { user_reported: "Reported", measured: "Record", estimated: "Model 1" };

const num = (v: unknown, digits = 0) => (typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: digits }) : "N/A");

export function FailureRiskPanel({ risk }: { risk: FailureRisk }) {
  const levels: RiskLevel[] = ["low", "moderate", "high"];
  const i = risk.inputs;
  const drivers: [string, string][] =
    risk.branch === "ice"
      ? [
          ["Age", `${num(i.vehicle_age)}y`],
          ["Mileage", `${num(i.km)} km · ${KM_SOURCE[String(i.km_source)] ?? i.km_source}`],
          ["Days since service", num(i.days_since_last_maintenance)],
          ["Past failures", num(i.failure_history)],
          ["Brand index", num(i.brand_reliability_index, 1)],
        ]
      : [
          ["Age", `${num(i.vehicle_age)}y`],
          ["Mileage", `${num(i.km)} km · ${KM_SOURCE[String(i.km_source)] ?? i.km_source}`],
          ["Km since service", num(i.last_service_distance)],
          ["Past failures", num(i.failure_history)],
          ["Brand index", num(i.brand_reliability_index, 1)],
        ];
  return (
    <article className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="failure-risk">
      <CardHeader
        eyebrow="Model 2 · Predictive maintenance"
        title="Predictive Maintenance Risk"
        right={
          <>
            <Tag tone="accent">{risk.branch === "ice" ? "ICE Engine Pipeline" : "EV / Hybrid Branch"}</Tag>
            <Tag>XGBoost Classifier</Tag>
          </>
        }
      />

      <div className="mt-5 flex flex-wrap items-center gap-5">
        <StatusPill status={LEVEL_PILL[risk.level]} size="lg">
          {LEVEL_NAME[risk.level]} risk
        </StatusPill>
        <div className="min-w-[220px] flex-1" role="img" aria-label={`${LEVEL_NAME[risk.level]} risk`}>
          <div className="flex h-4 gap-1.5">
            {levels.map((l) => (
              <div key={l} className={`flex-1 rounded-full ${l === risk.level ? SEGMENT[l].on : SEGMENT[l].off}`} />
            ))}
          </div>
          <div className="mt-1.5 flex text-[12px] font-semibold text-ink-faint">
            {levels.map((l) => (
              <span key={l} className={`flex-1 text-center ${l === risk.level ? "text-ink" : ""}`}>
                {LEVEL_NAME[l]}
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
