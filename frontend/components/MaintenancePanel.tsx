import type { MaintenanceInfo, RuleStatus } from "@/lib/types";
import { CardHeader, StatusPill, Tag, type RiskStatus } from "./ui/StatusPill";

const STATUS: Record<RuleStatus["status"], { pill: RiskStatus; text: string }> = {
  ok: { pill: "ok", text: "Up to date" },
  due_soon: { pill: "warn", text: "Due soon" },
  overdue: { pill: "critical", text: "Overdue" },
  no_record: { pill: "neutral", text: "No record" },
  no_record_overdue: { pill: "critical", text: "No record · overdue" },
};

/** "12 months or 15,000 km" -> "12m / 15,000 km" */
function shortInterval(interval: string): string {
  return interval.replace(/ months?/, "m").replace(" or ", " / ");
}

export function MaintenancePanel({ info }: { info: MaintenanceInfo }) {
  const b = info.odometer_basis.split(" (")[0];
  const basis = b.charAt(0).toUpperCase() + b.slice(1);
  return (
    <section className="card-shadow rounded-2xl border border-line bg-surface p-6">
      <CardHeader
        eyebrow="Rule-based fallback"
        title="Recommended Maintenance"
        right={<Tag>{`${basis}${info.odometer_used_km ? ` · ${info.odometer_used_km.toLocaleString("en-US")} km` : ""}`}</Tag>}
      />
      <ul className="mt-4 divide-y divide-line">
        {info.rules.map((r) => (
          <li key={r.key} className="flex items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-[14.5px] font-semibold text-ink">{r.label}</p>
              <p className="font-mono text-[12.5px] text-ink-soft">
                Every {shortInterval(r.interval)}
                {r.last_service_date ? ` · last ${r.last_service_date}` : ""}
              </p>
            </div>
            <StatusPill status={STATUS[r.status].pill}>{STATUS[r.status].text}</StatusPill>
          </li>
        ))}
      </ul>
    </section>
  );
}
