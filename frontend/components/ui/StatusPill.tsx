import type { ReactNode } from "react";

export type RiskStatus = "ok" | "warn" | "critical" | "neutral";

const STYLES: Record<RiskStatus, string> = {
  ok: "text-ok bg-ok-bg",
  warn: "text-warn bg-warn-bg",
  critical: "text-critical bg-critical-bg",
  neutral: "text-ink-faint bg-line/40",
};

export function StatusPill({ status, children }: { status: RiskStatus; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${STYLES[status]}`}
    >
      {children}
    </span>
  );
}
