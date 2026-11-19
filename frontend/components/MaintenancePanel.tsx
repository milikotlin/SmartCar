import type { MaintenanceInfo, RuleStatus } from "@/lib/types";
import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const STATUS: Record<RuleStatus["status"], { pill: RiskStatus; text: string }> = {
  ok: { pill: "ok", text: "Up to date" },
  due_soon: { pill: "warn", text: "Due soon" },
  overdue: { pill: "critical", text: "Overdue" },
  no_record: { pill: "neutral", text: "No record" },
  no_record_overdue: { pill: "critical", text: "No record, overdue" },
};

const cap = (t: string | null) => (t ? t.charAt(0).toUpperCase() + t.slice(1) + (t.endsWith(".") ? "" : ".") : null);

export function MaintenancePanel({ info }: { info: MaintenanceInfo }) {
  return (
    <section className="card-shadow rounded-[14px] border border-line bg-surface p-7">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Rules &middot; not machine learning</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Recommended maintenance</h2>
      <p className="mt-1 text-[13px] text-ink-soft">
        Generic service intervals applied to this vehicle&apos;s own records. Mileage basis: <strong className="text-ink">{info.odometer_basis}</strong>
        {info.odometer_used_km ? ` (${info.odometer_used_km.toLocaleString("en-US")} km)` : ""}.
      </p>

      <ul className="mt-5 divide-y divide-line">
        {info.rules.map((r) => (
          <li key={r.key} className="flex flex-wrap items-start justify-between gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-medium text-ink">{r.label}</p>
              <p className="text-[12px] text-ink-soft">
                Every {r.interval}.{" "}
                {r.last_service_date
                  ? `Last: ${r.last_service_date} at ${r.last_service_km?.toLocaleString("en-US")} km (${r.months_since} months ago${r.km_since !== null ? `, ${r.km_since.toLocaleString("en-US")} km since` : ""}).`
                  : cap(r.basis) ?? "No record on file."}
              </p>
              {r.attention && <p className="mt-0.5 text-[12px] text-ink">{r.advice}</p>}
            </div>
            <StatusPill status={STATUS[r.status].pill}>{STATUS[r.status].text}</StatusPill>
          </li>
        ))}
      </ul>
      <p className="mt-4 border-t border-line pt-3 text-[12px] text-ink-soft">{info.disclaimer}</p>
    </section>
  );
}
