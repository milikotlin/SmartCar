import type { FailureRisk, RiskLevel } from "@/lib/types";
import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const LEVEL_NAME: Record<RiskLevel, string> = { low: "Low", moderate: "Moderate", high: "High" };
const LEVEL_PILL: Record<RiskLevel, RiskStatus> = { low: "ok", moderate: "warn", high: "critical" };
const SEGMENT: Record<RiskLevel, { on: string; off: string }> = {
  low: { on: "bg-ok", off: "bg-ok-bg" },
  moderate: { on: "bg-warn", off: "bg-warn-bg" },
  high: { on: "bg-critical", off: "bg-critical-bg" },
};
const INPUT_LABEL: Record<string, string> = {
  vehicle_age: "Vehicle age (years)",
  km: "Mileage (km)",
  days_since_last_maintenance: "Days since the last maintenance",
  failure_history: "Recorded inspections with a defect",
  brand_reliability_index: "Brand reliability index (50 = average)",
  maintenance_type: "Type of the last maintenance",
  last_service_distance: "Km since the last service",
};
const KM_SOURCE: Record<string, string> = { user_reported: "reported by you", measured: "from a record", estimated: "Model 1 estimate" };

function fmt(key: string, value: unknown, kmSource?: string): string {
  if (typeof value === "number") {
    const n = key === "brand_reliability_index" ? value.toFixed(1) : Math.round(value).toLocaleString("en-US");
    return key === "km" && kmSource ? `${n} (${KM_SOURCE[kmSource] ?? kmSource})` : n;
  }
  return String(value);
}

export function FailureRiskPanel({ risk }: { risk: FailureRisk }) {
  const levels: RiskLevel[] = ["low", "moderate", "high"];
  const shown = Object.entries(risk.inputs).filter(([k]) => k in INPUT_LABEL);
  return (
    <article className="card-shadow rounded-[14px] border border-line bg-surface p-7" data-testid="failure-risk">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Machine learning &middot; Model 2</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Risk of a mechanical failure needing maintenance</h2>
      <p className="mt-1 text-[12.5px] text-ink-soft">Model used: {risk.branch_label}.</p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <StatusPill status={LEVEL_PILL[risk.level]}>{LEVEL_NAME[risk.level]} risk</StatusPill>
        <span className="text-[12px] text-ink-faint">{risk.level_rule}.</span>
      </div>
      <div className="mt-3" role="img" aria-label={`${LEVEL_NAME[risk.level]} risk`}>
        <div className="flex h-3 gap-1">
          {levels.map((l) => (
            <div key={l} className={`flex-1 rounded-sm ${l === risk.level ? SEGMENT[l].on : SEGMENT[l].off}`} />
          ))}
        </div>
        <div className="mt-1 flex text-[11px] text-ink-faint">
          {levels.map((l) => (
            <span key={l} className={`flex-1 text-center ${l === risk.level ? "font-semibold text-ink" : ""}`}>
              {LEVEL_NAME[l]}
            </span>
          ))}
        </div>
      </div>

      {risk.quality_note && (
        <p role="note" data-testid="failure-risk-quality" className="mt-4 rounded-md border border-warn bg-paper px-3 py-2 text-[12.5px] leading-relaxed text-ink">
          <strong className="font-semibold text-warn">What this level is worth here.</strong> {risk.quality_note}
        </p>
      )}
      <div className="mt-4 rounded-[10px] border border-line bg-paper px-4 py-3 text-[12.5px] leading-relaxed text-ink-soft">
        <p>{risk.disclaimer}</p>
        {risk.assumed.length > 0 && (
          <p className="mt-1.5" data-testid="failure-risk-assumed">
            <strong className="text-ink">Not known for this vehicle, replaced by a typical value:</strong> {risk.assumed.join(", ")}.
          </p>
        )}
      </div>

      <details className="mt-4 text-[12.5px] text-ink-soft">
        <summary className="cursor-pointer font-medium text-ink">Inputs, how the levels were set, and how this model compares</summary>
        <div className="mt-3 space-y-3">
          <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
            {shown.map(([k, v]) => (
              <div key={k} className="contents">
                <dt>{INPUT_LABEL[k]}</dt>
                <dd className="text-right font-mono text-ink">{fmt(k, v, risk.inputs.km_source as string | undefined)}</dd>
              </div>
            ))}
          </dl>
          <p>
            <strong className="text-ink">Levels:</strong> in the held-out part of the training data, the share of vehicles marked &ldquo;maintenance required&rdquo; was{" "}
            {levels.map((l, i) => `${LEVEL_NAME[l]} ${risk.observed_rate_by_level[i] ?? "—"}%`).join(", ")} (synthetic data, not real vehicles).
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <caption className="mb-1 text-left text-ink">How well each model ranks vehicles (ROC-AUC: 0.5 = chance, 1 = perfect)</caption>
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-ink-faint">
                  <th className="py-1 pr-3">Model</th>
                  <th className="py-1 pr-3">Data</th>
                  <th className="py-1 pr-3">Test</th>
                  <th className="py-1 text-right">ROC-AUC</th>
                </tr>
              </thead>
              <tbody>
                {risk.comparison.map((r) => (
                  <tr key={`${r.model}-${r.data}`} className="border-t border-line">
                    <td className="py-1 pr-3 text-ink">{r.model}</td>
                    <td className="py-1 pr-3">{r.data}</td>
                    <td className="py-1 pr-3">{r.test}</td>
                    <td className="py-1 text-right font-mono text-ink">{r.roc_auc?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11.5px] text-ink-faint">A score on synthetic data says how well the model learned the dataset&apos;s own rules; only the rows on real inspections say how well it ranks real vehicles.</p>
        </div>
      </details>
    </article>
  );
}
