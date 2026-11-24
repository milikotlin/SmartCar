import { useTranslations } from "next-intl";
import { useFmt } from "@/lib/format";
import type { MaintenanceInfo, RuleStatus } from "@/lib/types";
import { CardHeader, StatusPill, Tag, type RiskStatus } from "./ui/StatusPill";

const STATUS_PILL: Record<RuleStatus["status"], RiskStatus> = { ok: "ok", due_soon: "warn", overdue: "critical", no_record: "neutral", no_record_overdue: "critical" };

export function MaintenancePanel({ info }: { info: MaintenanceInfo }) {
  const t = useTranslations("maintenance");
  const { num, km } = useFmt();
  const basis = t(`basis.${(info.odometer_basis_code ?? "odo_estimated") as "odo_reported" | "odo_measured" | "odo_estimated"}`);
  const interval = (r: RuleStatus) =>
    r.interval_months && r.interval_km ? t("intervalBoth", { months: r.interval_months, km: num(r.interval_km) }) : r.interval_months ? t("intervalMonths", { months: r.interval_months }) : r.interval;
  return (
    <section className="card-shadow rounded-2xl border border-line bg-surface p-6">
      <CardHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        right={<Tag>{`${basis}${info.odometer_used_km ? ` · ${km(info.odometer_used_km)}` : ""}`}</Tag>}
      />
      <ul className="mt-4 divide-y divide-line">
        {info.rules.map((r) => (
          <li key={r.key} className="flex items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-[14.5px] font-semibold text-ink">{r.label}</p>
              <p className="font-mono text-[12.5px] text-ink-soft">
                {t("every", { interval: interval(r) })}
                {r.last_service_date ? t("last", { date: r.last_service_date }) : ""}
              </p>
            </div>
            <StatusPill status={STATUS_PILL[r.status]}>{t(`status.${r.status}`)}</StatusPill>
          </li>
        ))}
      </ul>
    </section>
  );
}
