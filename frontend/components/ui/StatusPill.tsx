import type { ReactNode } from "react";

export type RiskStatus = "ok" | "warn" | "critical" | "neutral";

const STYLES: Record<RiskStatus, string> = {
  ok: "text-ok bg-ok-bg",
  warn: "text-warn bg-warn-bg",
  critical: "text-critical bg-critical-bg",
  neutral: "text-ink-soft bg-chip",
};

const SIZES = {
  sm: "px-2.5 py-1 text-[11px]",
  md: "px-3 py-1.5 text-[12.5px]",
  lg: "px-4 py-2 text-[15px]",
};

export function StatusPill({ status, children, size = "sm" }: { status: RiskStatus; children: ReactNode; size?: keyof typeof SIZES }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full font-bold uppercase tracking-wide ${SIZES[size]} ${STYLES[status]}`}>{children}</span>;
}

/** Small neutral tag: "XGBoost Regressor", "Days since service: N/A" ... */
export function Tag({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "accent" | "warn"; title?: string }) {
  const t = tone === "accent" ? "border-accent/40 text-accent" : tone === "warn" ? "border-warn/50 text-warn" : "border-line-strong text-ink-soft";
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-2 py-1 font-mono text-[11.5px] font-medium ${t}`}>
      {children}
    </span>
  );
}

/** Card section header: eyebrow + title + optional badges on the right. */
export function CardHeader({ eyebrow, title, right }: { eyebrow: string; title: string; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[11.5px] font-bold uppercase tracking-[0.12em] text-ink-faint">{eyebrow}</p>
        <h2 className="mt-1 text-[19px] font-bold tracking-tight text-ink">{title}</h2>
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}
