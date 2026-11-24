import { useTranslations, type Messages } from "next-intl";
import { useFmt } from "@/lib/format";
import type { FailureRisk, InspectionRisk } from "@/lib/types";

const LEVELS = ["low", "moderate", "high"] as const;
type Feature = keyof Messages["metrics"]["features"];

const th = "py-2 pe-3 text-start text-[11px] font-bold uppercase tracking-wider text-ink-faint";
const td = "py-1.5 pe-3 text-[13px]";

export function MlMetricsDrawer({ failure, inspection }: { failure: FailureRisk | null; inspection: InspectionRisk }) {
  const t = useTranslations("metrics");
  const tLevel = useTranslations("levels");
  const { num } = useFmt();
  const value = (v: unknown) =>
    typeof v === "number" ? (Math.abs(v) < 1 && v !== 0 ? v.toFixed(4) : num(v, 1)) : t.has(`kmSource.${String(v)}` as "kmSource.measured") ? t(`kmSource.${String(v)}` as "kmSource.measured") : String(v);
  const feature = (k: string) => (t.has(`features.${k}` as `features.${Feature}`) ? t(`features.${k}` as `features.${Feature}`) : k);
  return (
    <details className="group card-shadow rounded-2xl border border-line bg-surface" data-testid="ml-metrics">
      <summary className="flex min-h-14 cursor-pointer items-center justify-between px-6 text-[15px] font-bold text-ink">
        <span>{t("title")}</span>
        <span className="text-ink-faint transition-transform group-open:rotate-180">▾</span>
      </summary>
      <div className="grid gap-6 border-t border-line px-6 py-5 min-[1100px]:grid-cols-2">
        {failure && (
          <section>
            <h3 className="text-[13px] font-bold uppercase tracking-wider text-ink">{t("benchmarks")}</h3>
            <table className="mt-2 w-full border-collapse">
              <thead>
                <tr>
                  <th className={th}>{t("model")}</th>
                  <th className={th}>{t("testData")}</th>
                  <th className={`${th} text-end`}>{t("auc")}</th>
                </tr>
              </thead>
              <tbody>
                {failure.comparison.map((r) => (
                  <tr key={`${r.model}-${r.data}`} className="border-t border-line">
                    <td className={`${td} font-semibold text-ink`}>{r.model}</td>
                    <td className={`${td} text-ink-soft`}>{r.data}</td>
                    <td className={`${td} text-end font-mono font-bold text-ink`}>{r.roc_auc?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3 className="mt-5 text-[13px] font-bold uppercase tracking-wider text-ink">{t("defectRate")}</h3>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {LEVELS.map((l, i) => (
                <div key={l} className="rounded-lg bg-chip px-3 py-2 text-center">
                  <p className="text-[11px] font-bold uppercase text-ink-faint">{tLevel(l)}</p>
                  <p className="font-mono text-[17px] font-bold text-ink">{failure.observed_rate_by_level[i] ?? "—"}%</p>
                </div>
              ))}
            </div>
          </section>
        )}
        <section>
          {failure && (
            <>
              <h3 className="text-[13px] font-bold uppercase tracking-wider text-ink">{t("vector", { branch: failure.branch === "ice" ? t("branchIce") : t("branchEv") })}</h3>
              <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 font-mono text-[12.5px]">
                {Object.entries(failure.inputs).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="truncate text-ink-soft">{feature(k)}</dt>
                    <dd className="text-end font-bold text-ink">{value(v)}</dd>
                  </div>
                ))}
              </dl>
              {failure.assumed.length > 0 && (
                <p className="mt-2 text-[12.5px] text-ink-soft" data-testid="failure-risk-assumed">
                  <span className="font-bold text-ink">{t("notKnown")}</span> {failure.assumed.join(", ")}
                </p>
              )}
            </>
          )}
          {inspection.covered && inspection.scale && (
            <>
              <h3 className="mt-5 text-[13px] font-bold uppercase tracking-wider text-ink">{t("ukRate")}</h3>
              <table className="mt-2 w-full border-collapse">
                <thead>
                  <tr>
                    <th className={th}>{t("system")}</th>
                    {LEVELS.map((l) => (
                      <th key={l} className={`${th} text-end`}>
                        {tLevel(l)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {inspection.systems.map((s) => (
                    <tr key={s.system} className="border-t border-line">
                      <td className={`${td} font-semibold text-ink`}>{s.title.split(" (")[0]}</td>
                      <td className={`${td} text-end font-mono text-ink`}>{s.observed_in_reference.low}%</td>
                      <td className={`${td} text-end font-mono text-ink`}>{s.observed_in_reference.moderate}%</td>
                      <td className={`${td} text-end font-mono text-ink`}>{s.observed_in_reference.high}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[12px] text-ink-faint">
                {t("cuts", { low: inspection.scale.cut_percentiles.brakes[0], high: inspection.scale.cut_percentiles.brakes[1] })}
              </p>
            </>
          )}
        </section>
      </div>
    </details>
  );
}
