import type { InspectionRisk } from "@/lib/types";
import { RiskLevelBar } from "./RiskLevelBar";
import { CardHeader, StatusPill, Tag } from "./ui/StatusPill";

const VARIANT_TAG: Record<string, string> = {
  cold: "Registry only",
  cold_odo: "+ Odometer",
  hist: "+ Last inspection",
  hist_odo: "+ Inspection + odometer",
};

/** Backend coverage reasons -> 2-3 word chips. */
function reasonChip(reason: string): string {
  const r = reason.toLowerCase();
  if (r.includes("fuel type")) return "Fuel not covered";
  if (r.includes("under")) return "Under 3 years";
  if (r.includes("more than")) return "Over 20 years";
  return "Outside coverage";
}

export function RiskPanel({ risk }: { risk: InspectionRisk }) {
  return (
    <article className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="comparison-risk">
      <CardHeader
        eyebrow="Comparison · UK MOT real inspections"
        title="Subsystem Risk"
        right={
          risk.covered ? (
            <>
              <Tag tone="accent">{risk.variant ? VARIANT_TAG[risk.variant] : "Registry only"}</Tag>
              {risk.odometer_source === "user_reported" && <Tag>Odometer: reported</Tag>}
              <Tag>XGBoost × 3</Tag>
            </>
          ) : undefined
        }
      />

      {risk.covered && risk.scale ? (
        <div className="mt-5 grid grid-cols-3 gap-3 max-[900px]:grid-cols-1">
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
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-line-strong bg-paper px-4 py-4" data-testid="comparison-not-covered">
          <StatusPill status="neutral" size="md">
            Not covered
          </StatusPill>
          <span className="text-[14px] font-semibold text-ink">No estimate for this vehicle</span>
          {risk.reasons.map((r) => (
            <Tag key={r} title={r}>
              {reasonChip(r)}
            </Tag>
          ))}
        </div>
      )}
    </article>
  );
}
