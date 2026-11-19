import type { RiskLevel, SameAgeLabel } from "@/lib/types";
import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const LEVEL_NAME: Record<RiskLevel, string> = { low: "Low", moderate: "Moderate", high: "High" };
const LEVEL_PILL: Record<RiskLevel, RiskStatus> = { low: "ok", moderate: "warn", high: "critical" };
const SEGMENT_STYLE: Record<RiskLevel, { on: string; off: string }> = {
  low: { on: "bg-ok", off: "bg-ok-bg" },
  moderate: { on: "bg-warn", off: "bg-warn-bg" },
  high: { on: "bg-critical", off: "bg-critical-bg" },
};
const SAME_AGE_TEXT: Record<SameAgeLabel, string> = {
  lower: "lower than most vehicles of that age",
  typical: "about typical for that age",
  higher: "higher than most vehicles of that age",
};

interface Props {
  title: string;
  level: RiskLevel;
  /** "Higher than about N of 100 reference vehicles" (rank, rounded to 5). */
  higherThan: number;
  /** Boundaries between Low/Moderate and Moderate/High as percentiles of the reference vehicles (they set the segment widths). */
  cuts: [number, number];
  sameAgeLabel: SameAgeLabel;
  sameAgeYears: number;
}

export function RiskLevelBar({ title, level, higherThan, cuts, sameAgeLabel, sameAgeYears }: Props) {
  const widths: Record<RiskLevel, number> = { low: cuts[0], moderate: cuts[1] - cuts[0], high: 100 - cuts[1] };
  // "Engine-related (emissions, fuel, mounts)" -> heading "Engine-related" and a caption, so that the three cards have the same layout
  const [name, ...rest] = title.split(" (");
  const caption = rest.length ? rest.join(" (").replace(/\)$/, "") : "";
  return (
    <div className="flex flex-col rounded-[10px] border border-line bg-paper px-4 py-4" data-testid={`risk-${title}`}>
      <h3 className="text-[14px] font-semibold text-ink">{name}</h3>
      <p className="min-h-[18px] text-[11.5px] text-ink-faint">{caption}</p>
      <div className="mt-2">
        <StatusPill status={LEVEL_PILL[level]}>{LEVEL_NAME[level]} relative risk</StatusPill>
      </div>

      <div className="relative mt-4" role="img" aria-label={`${title}: ${LEVEL_NAME[level]} relative risk, higher than about ${higherThan} of 100 reference vehicles`}>
        <div className="flex h-3 w-full overflow-hidden rounded-full">
          {(["low", "moderate", "high"] as const).map((l) => (
            <div key={l} style={{ width: `${widths[l]}%` }} className={l === level ? SEGMENT_STYLE[l].on : SEGMENT_STYLE[l].off} />
          ))}
        </div>
        <div className="absolute top-[-5px] h-[22px] w-[3px] -translate-x-1/2 rounded bg-ink" style={{ left: `${higherThan}%` }} aria-hidden="true" />
        <div className="mt-1.5 flex text-[11px] text-ink-faint">
          {(["low", "moderate", "high"] as const).map((l) => (
            <span key={l} style={{ width: `${widths[l]}%` }} className="truncate text-center">
              {LEVEL_NAME[l]}
            </span>
          ))}
        </div>
      </div>

      <p className="mt-3 text-[13px] text-ink">
        Higher than about <strong>{higherThan}</strong> of 100 reference vehicles.
      </p>
      <p className="mt-1 text-[12px] text-ink-soft">
        Compared with vehicles aged {sameAgeYears} only: <span className="font-medium text-ink">{SAME_AGE_TEXT[sameAgeLabel]}</span>.
      </p>
    </div>
  );
}
