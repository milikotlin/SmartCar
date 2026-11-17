import { StatusPill, type RiskStatus } from "./ui/StatusPill";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const STATUS_COLOR: Record<Exclude<RiskStatus, "neutral">, string> = {
  ok: "var(--color-ok)",
  warn: "var(--color-warn)",
  critical: "var(--color-critical)",
};

const STATUS_LABEL: Record<Exclude<RiskStatus, "neutral">, string> = {
  ok: "OK",
  warn: "Attention",
  critical: "Critical",
};

interface RiskGaugeProps {
  label: string;
  percent?: number;
  status?: Exclude<RiskStatus, "neutral">;
}

export function RiskGauge({ label, percent, status }: RiskGaugeProps) {
  const hasData = percent !== undefined && status !== undefined;
  const dash = hasData ? (percent / 100) * CIRCUMFERENCE : 0;

  return (
    <div className="flex flex-col items-center gap-3.5 rounded-[10px] border border-line bg-paper px-3 py-5">
      <svg viewBox="0 0 120 120" className="h-[108px] w-[108px]">
        <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="var(--color-line-strong)" strokeWidth="9" />
        {hasData && (
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            stroke={STATUS_COLOR[status]}
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${CIRCUMFERENCE}`}
            transform="rotate(-90 60 60)"
          />
        )}
        <text
          x="60"
          y="66"
          textAnchor="middle"
          fill="var(--color-ink)"
          className="font-mono text-[22px] font-semibold"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {hasData ? `${percent}%` : "—"}
        </text>
      </svg>
      <span className="text-[13px] font-semibold text-ink">{label}</span>
      {hasData ? <StatusPill status={status}>{STATUS_LABEL[status]}</StatusPill> : <StatusPill status="neutral">Pending</StatusPill>}
    </div>
  );
}
