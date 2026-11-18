import type { InspectionRisk } from "@/lib/types";
import { RiskGauge } from "./RiskGauge";

const VARIANT_TEXT: Record<string, string> = {
  cold: "Registry data only",
  cold_odo: "Registry data + measured odometer",
  hist: "Registry data + previous inspection result",
  hist_odo: "Registry data + previous inspection result + measured odometer",
};

export function RiskPanel({ risk }: { risk: InspectionRisk }) {
  return (
    <article className="card-shadow rounded-[14px] border border-line bg-surface p-7">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Machine learning &middot; Model 2</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Estimated inspection-defect risk</h2>
      <p className="mt-1 text-[13px] text-ink-soft">Risk that the next annual inspection finds a defect in each system</p>

      {risk.covered ? (
        <>
          <div className="mt-6 grid grid-cols-3 gap-5 max-[640px]:grid-cols-1">
            {risk.systems.map((s) => (
              <RiskGauge key={s.system} label={s.title} percentile={s.percentile_same_age} band={s.band} />
            ))}
          </div>
          <details className="mt-5 text-[12.5px] text-ink-soft">
            <summary className="cursor-pointer font-medium text-ink">Model details and reference figures</summary>
            <ul className="mt-2 space-y-1.5">
              {risk.systems.map((s) => (
                <li key={s.system}>
                  <span className="font-medium text-ink">{s.title}:</span> {s.explanation} Reference only: {(s.foreign_probability * 100).toFixed(1)}% as calibrated on UK inspections (not a validated probability for Israel).
                </li>
              ))}
              <li>
                <span className="font-medium text-ink">Inputs used:</span> {risk.variant ? VARIANT_TEXT[risk.variant] : "—"}.
              </li>
              {risk.reasons.map((r) => (
                <li key={r}>Note: {r}.</li>
              ))}
            </ul>
          </details>
        </>
      ) : (
        <div className="mt-6 rounded-[10px] border border-dashed border-line-strong bg-paper px-5 py-6 text-[13.5px] text-ink-soft">
          <p className="font-medium text-ink">No estimate for this vehicle</p>
          <ul className="mt-1.5 list-disc pl-5">
            {risk.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-2">The model was trained on petrol, diesel and hybrid cars tested at 3 to 20 years of age. See the maintenance and recall panels below for what is known.</p>
        </div>
      )}

      <p className="mt-5 border-t border-line pt-4 text-[12.5px] text-ink-soft">
        <strong className="font-semibold text-ink">What this is.</strong> {risk.definition} {risk.disclaimer}
      </p>
    </article>
  );
}
