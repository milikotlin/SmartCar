import type { InspectionRisk } from "@/lib/types";
import { RiskLevelBar } from "./RiskLevelBar";

const VARIANT_TEXT: Record<string, string> = {
  cold: "registry data only (age, make, fuel)",
  cold_odo: "registry data and the measured odometer",
  hist: "registry data and the result of the previous annual inspection",
  hist_odo: "registry data, the result of the previous annual inspection and the measured odometer",
};

export function RiskPanel({ risk }: { risk: InspectionRisk }) {
  return (
    <article className="card-shadow rounded-[14px] border border-line bg-surface p-7">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Machine learning &middot; Model 2</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Risk of a defect at the next annual inspection</h2>

      {risk.covered && risk.scale ? (
        <>
      <div className="mt-3 rounded-[10px] border border-line bg-paper px-4 py-3 text-[13px] leading-relaxed text-ink-soft">
        <p>
          <strong className="font-semibold text-ink">How to read this.</strong> Each bar compares the vehicle with <strong className="text-ink">reference vehicles of all ages</strong> from UK
          inspection data: the further to the right, the higher the estimated risk that the next annual inspection finds a defect in that system. The same scale is used for
          every vehicle, so two vehicles can be compared directly.
        </p>
        <p className="mt-1.5">
          Older cars have more defects at inspection, so they usually sit further right. This is a <strong className="text-ink">relative level</strong>, not a probability and not a
          prediction of a breakdown, and it has not been validated for Israeli vehicles.
        </p>
      </div>

          <div className="mt-5 grid grid-cols-3 gap-4 max-[900px]:grid-cols-1">
            {risk.systems.map((s) => (
              <RiskLevelBar
                key={s.system}
                title={s.title}
                level={s.level}
                higherThan={s.higher_than_of_100}
                cuts={risk.scale!.cut_percentiles[s.system]}
                sameAgeLabel={s.same_age_label}
                sameAgeYears={s.same_age_years}
              />
            ))}
          </div>

          <details className="mt-5 text-[12.5px] text-ink-soft">
            <summary className="cursor-pointer font-medium text-ink">What the levels mean and what the reference data show</summary>
            <div className="mt-3 space-y-3">
              <p>
                <strong className="text-ink">Reference:</strong> {risk.scale.reference}. {risk.scale.interval}. The vehicle is placed among the reference vehicles by the model&apos;s own
                estimate, using {risk.variant ? VARIANT_TEXT[risk.variant] : "the available data"}.
              </p>
              <p>
                <strong className="text-ink">How much comes from age:</strong> most of the level reflects the age of the vehicle (age alone already ranks vehicles almost as well). The model adds a smaller
                part, larger when the result of the previous inspection or the measured odometer is known; the same-age line shows that part.
              </p>
              <p>
                <strong className="text-ink">Where the levels start:</strong> the cut points were chosen from the data, so that the three levels best separate how often a defect was
                actually found at the next inspection, with each level holding at least a fifth of the reference vehicles.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left">
                  <caption className="mb-1 text-left text-ink">How often a defect was found at the next inspection in the UK reference data</caption>
                  <thead>
                    <tr className="text-[11px] uppercase tracking-wide text-ink-faint">
                      <th className="border-b border-line py-1.5 pr-3 font-semibold">System</th>
                      <th className="border-b border-line py-1.5 pr-3 font-semibold">Low</th>
                      <th className="border-b border-line py-1.5 pr-3 font-semibold">Moderate</th>
                      <th className="border-b border-line py-1.5 font-semibold">High</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risk.systems.map((s) => (
                      <tr key={s.system}>
                        <td className="border-b border-line py-1.5 pr-3 text-ink">{s.title}</td>
                        <td className="border-b border-line py-1.5 pr-3">about {s.observed_in_reference.low}%</td>
                        <td className="border-b border-line py-1.5 pr-3">about {s.observed_in_reference.moderate}%</td>
                        <td className="border-b border-line py-1.5">about {s.observed_in_reference.high}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>
                These are frequencies of <em>groups of reference vehicles</em>, not a forecast for this vehicle. {risk.scale.country_note}
              </p>
              <p>
                <strong className="text-ink">The complementary line</strong> (&quot;compared with vehicles aged N only&quot;) ignores age on purpose: it tells whether the vehicle is better or worse
                than its age group, not whether it is riskier than a vehicle of another age.
              </p>
              {risk.reasons.length > 0 && (
                <ul className="list-disc pl-5">
                  {risk.reasons.map((r) => (
                    <li key={r}>Note: {r}.</li>
                  ))}
                </ul>
              )}
            </div>
          </details>
        </>
      ) : (
        <div className="mt-5 rounded-[10px] border border-dashed border-line-strong bg-paper px-5 py-6 text-[13.5px] text-ink-soft">
          <p className="font-medium text-ink">No estimate for this vehicle</p>
          <ul className="mt-1.5 list-disc pl-5">
            {risk.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-2">The model learns from petrol, diesel and hybrid cars that have already had annual inspections, between 3 and 20 years of age. For other vehicles no risk estimate is shown rather than guessing one. The estimated mileage, the recommended maintenance and the official recalls below still apply.</p>
        </div>
      )}

      {risk.covered && <p className="mt-5 border-t border-line pt-4 text-[12.5px] text-ink-soft">{risk.disclaimer}</p>}
    </article>
  );
}
