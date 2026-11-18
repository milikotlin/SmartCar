import type { RiskBand } from "@/lib/types";
import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const BAND_STATUS: Record<RiskBand, RiskStatus> = { lower: "ok", typical: "neutral", higher: "warn" };
const BAND_COLOR: Record<RiskBand, string> = { lower: "var(--color-ok)", typical: "var(--color-ink-faint)", higher: "var(--color-warn)" };
const BAND_LABEL: Record<RiskBand, string> = { lower: "Lower than similar", typical: "Typical for its age", higher: "Higher than similar" };

interface RiskGaugeProps {
  label: string;
  /** Rank among vehicles of the same age (1-99). This is a rank, not a probability. */
  percentile?: number;
  band?: RiskBand;
}

export function RiskGauge({ label, percentile, band }: RiskGaugeProps) {
  const hasData = percentile !== undefined && band !== undefined;
  const dash = hasData ? (percentile / 100) * CIRCUMFERENCE : 0;

  return (
    <div className="flex flex-col items-center gap-3 rounded-[10px] border border-line bg-paper px-3 py-5 text-center">
      <svg viewBox="0 0 120 120" className="h-[108px] w-[108px]" role="img" aria-label={hasData ? `${label}: ${BAND_LABEL[band]}, rank ${percentile} of 100` : `${label}: not available`}>
        <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="var(--color-line-strong)" strokeWidth="9" />
        {hasData && (
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke={BAND_COLOR[band]}
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${CIRCUMFERENCE}`}
            transform="rotate(-90 60 60)"
          />
        )}
        <text x="60" y="58" textAnchor="middle" fill="var(--color-ink)" className="font-mono text-[24px] font-semibold" style={{ fontVariantNumeric: "tabular-nums" }}>
          {hasData ? percentile : "—"}
        </text>
        <text x="60" y="76" textAnchor="middle" fill="var(--color-ink-faint)" className="text-[9px] uppercase tracking-wider">
          {hasData ? "rank of 100" : ""}
        </text>
      </svg>
      <span className="text-[13px] font-semibold text-ink">{label}</span>
      {hasData ? <StatusPill status={BAND_STATUS[band]}>{BAND_LABEL[band]}</StatusPill> : <StatusPill status="neutral">Not covered</StatusPill>}
    </div>
  );
}
