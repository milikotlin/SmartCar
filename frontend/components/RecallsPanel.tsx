import { useTranslations } from "next-intl";
import type { RecallInfo } from "@/lib/types";
import { CardHeader, StatusPill, Tag } from "./ui/StatusPill";

export function RecallsPanel({ info }: { info: RecallInfo }) {
  const t = useTranslations("recalls");
  return (
    <section className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="recalls">
      <CardHeader eyebrow={t("eyebrow")} title={t("title")} right={<Tag>{t("source")}</Tag>} />
      {!info.available ? (
        <p className="mt-4 flex items-center gap-3 text-[14px] font-semibold text-ink">
          <StatusPill status="neutral" size="md">
            {t("unavailable")}
          </StatusPill>
          {t("offline")}
        </p>
      ) : info.count === 0 ? (
        <p className="mt-4 flex items-center gap-3 text-[15px] font-semibold text-ink">
          <StatusPill status="ok" size="md">
            {t("none")}
          </StatusPill>
          {t("noOpen")}
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-line">
          {info.items.map((r, i) => (
            <li key={`${r.recall_id}-${i}`} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[15px] font-bold text-ink">{r.category}</p>
                <StatusPill status="critical" size="md">
                  {t("open")}
                </StatusPill>
              </div>
              <p className="mt-0.5 font-mono text-[12.5px] text-ink-soft">
                {r.type} · {r.opened ?? "—"} · #{r.recall_id}
              </p>
              {r.description_he && (
                <p dir="rtl" className="mt-1 text-[13px] leading-relaxed text-ink-soft">
                  {r.description_he}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
