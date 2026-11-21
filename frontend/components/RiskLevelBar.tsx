import type { RiskLevel, SameAgeLabel } from "@/lib/types";
import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const LEVEL_NAME: Record<RiskLevel, string> = { low: "Low", moderate: "Moderate", high: "High" };
const LEVEL_PILL: Record<RiskLevel, RiskStatus> = { low: "ok", moderate: "warn", high: "critical" };
const SEGMENT_STYLE: Record<RiskLevel, { on: string; off: string }> = {
  low: { on: "bg-ok", off: "bg-ok-bg" },
  moderate: { on: "bg-warn", off: "bg-warn-bg" },
  high: { on: "bg-critical", off: "bg-critical-bg" },
};
const SAME_AGE: Record<SameAgeLabel, string> = { lower: "below peers", typical: "typical", higher: "above peers" };

interface Props {
  title: string;
  level: RiskLevel;
  /** Percentile among all reference vehicles (rounded to 5). */
  higherThan: number;
  /** Low/Moderate and Moderate/High boundaries as percentiles (they set the segment widths). */
  cuts: [number, number];
  sameAgeLabel: SameAgeLabel;
  sameAgeYears: number;
}

export function RiskLevelBar({ title, level, higherThan, cuts, sameAgeLabel, sameAgeYears }: Props) {
  const widths: Record<RiskLevel, number> = { low: cuts[0], moderate: cuts[1] - cuts[0], high: 100 - cuts[1] };
  const name = title.split(" (")[0];
  return (
    <div className="flex flex-col rounded-xl border border-line bg-paper p-4" data-testid={`risk-${title}`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[15px] font-bold text-ink">{name}</h3>
        <StatusPill status={LEVEL_PILL[level]} size="md">
          {LEVEL_NAME[level]}
        </StatusPill>
      </div>

      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="font-mono text-[30px] font-bold leading-none text-ink">P{higherThan}</span>
        <span className="text-[12px] font-semibold text-ink-faint">percentile</span>
      </div>

      <div className="relative mt-3" role="img" aria-label={`${name}: ${LEVEL_NAME[level]}, percentile ${higherThan} of the reference vehicles`}>
        <div className="flex h-3 w-full overflow-hidden rounded-full">
          {(["low", "moderate", "high"] as const).map((l) => (
            <div key={l} style={{ width: `${widths[l]}%` }} className={l === level ? SEGMENT_STYLE[l].on : SEGMENT_STYLE[l].off} />
          ))}
        </div>
        <div className="absolute top-[-5px] h-[22px] w-[3px] -translate-x-1/2 rounded bg-ink" style={{ left: `${higherThan}%` }} aria-hidden="true" />
      </div>

      <p className="mt-3 text-[12.5px] font-semibold text-ink-soft">
        Age {sameAgeYears}: <span className="text-ink">{SAME_AGE[sameAgeLabel]}</span>
      </p>
    </div>
  );
}
