import type { FailureRisk, InspectionRisk } from "@/lib/types";

const LEVELS = ["Low", "Moderate", "High"];
const INPUT_LABEL: Record<string, string> = {
  vehicle_age: "vehicle_age",
  km: "km",
  km_source: "km_source",
  days_since_last_maintenance: "days_since_last_maintenance",
  failure_history: "failure_history",
  brand_reliability_index: "brand_reliability_index",
  d4_engine_fault_rate: "d4_engine_fault_rate",
  d4_brake_fault_rate: "d4_brake_fault_rate",
  d4_battery_fault_rate: "d4_battery_fault_rate",
  maintenance_type: "maintenance_type",
  last_service_distance: "last_service_distance",
};

function fmt(v: unknown): string {
  if (typeof v === "number") return Math.abs(v) < 1 && v !== 0 ? v.toFixed(4) : v.toLocaleString("en-US", { maximumFractionDigits: 1 });
  return String(v);
}

const th = "py-2 pr-3 text-left text-[11px] font-bold uppercase tracking-wider text-ink-faint";
const td = "py-1.5 pr-3 text-[13px]";

export function MlMetricsDrawer({ failure, inspection }: { failure: FailureRisk | null; inspection: InspectionRisk }) {
  return (
    <details className="group card-shadow rounded-2xl border border-line bg-surface" data-testid="ml-metrics">
      <summary className="flex min-h-14 cursor-pointer items-center justify-between px-6 text-[15px] font-bold text-ink">
        <span>ML Metrics &amp; Feature Vector</span>
        <span className="text-ink-faint transition-transform group-open:rotate-180">▾</span>
      </summary>
      <div className="grid gap-6 border-t border-line px-6 py-5 min-[1100px]:grid-cols-2">
        {failure && (
          <section>
            <h3 className="text-[13px] font-bold uppercase tracking-wider text-ink">Benchmarks · ROC-AUC</h3>
            <table className="mt-2 w-full border-collapse">
              <thead>
                <tr>
                  <th className={th}>Model</th>
                  <th className={th}>Test data</th>
                  <th className={`${th} text-right`}>AUC</th>
                </tr>
              </thead>
              <tbody>
                {failure.comparison.map((r) => (
                  <tr key={`${r.model}-${r.data}`} className="border-t border-line">
                    <td className={`${td} font-semibold text-ink`}>{r.model}</td>
                    <td className={`${td} text-ink-soft`}>{r.data}</td>
                    <td className={`${td} text-right font-mono font-bold text-ink`}>{r.roc_auc?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3 className="mt-5 text-[13px] font-bold uppercase tracking-wider text-ink">Model 2 · held-out rate by level</h3>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {LEVELS.map((l, i) => (
                <div key={l} className="rounded-lg bg-chip px-3 py-2 text-center">
                  <p className="text-[11px] font-bold uppercase text-ink-faint">{l}</p>
                  <p className="font-mono text-[17px] font-bold text-ink">{failure.observed_rate_by_level[i] ?? "—"}%</p>
                </div>
              ))}
            </div>
          </section>
        )}
        <section>
          {failure && (
            <>
              <h3 className="text-[13px] font-bold uppercase tracking-wider text-ink">Model 2 · feature vector ({failure.branch === "ice" ? "ICE" : "EV / hybrid"})</h3>
              <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 font-mono text-[12.5px]">
                {Object.entries(failure.inputs).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="truncate text-ink-soft">{INPUT_LABEL[k] ?? k}</dt>
                    <dd className="text-right font-bold text-ink">{fmt(v)}</dd>
                  </div>
                ))}
              </dl>
              {failure.assumed.length > 0 && (
                <p className="mt-2 text-[12.5px] text-ink-soft" data-testid="failure-risk-assumed">
                  <span className="font-bold text-ink">Median-imputed:</span> {failure.assumed.join(", ")}
                </p>
              )}
            </>
          )}
          {inspection.covered && inspection.scale && (
            <>
              <h3 className="mt-5 text-[13px] font-bold uppercase tracking-wider text-ink">UK MOT model · defect rate by level</h3>
              <table className="mt-2 w-full border-collapse">
                <thead>
                  <tr>
                    <th className={th}>System</th>
                    {LEVELS.map((l) => (
                      <th key={l} className={`${th} text-right`}>
                        {l}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {inspection.systems.map((s) => (
                    <tr key={s.system} className="border-t border-line">
                      <td className={`${td} font-semibold text-ink`}>{s.title.split(" (")[0]}</td>
                      <td className={`${td} text-right font-mono text-ink`}>{s.observed_in_reference.low}%</td>
                      <td className={`${td} text-right font-mono text-ink`}>{s.observed_in_reference.moderate}%</td>
                      <td className={`${td} text-right font-mono text-ink`}>{s.observed_in_reference.high}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[12px] text-ink-faint">
                Level cuts P{inspection.scale.cut_percentiles.brakes[0]} / P{inspection.scale.cut_percentiles.brakes[1]} · 12-month interval
              </p>
            </>
          )}
        </section>
      </div>
    </details>
  );
}
