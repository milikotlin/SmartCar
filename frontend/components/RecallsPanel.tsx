import type { RecallInfo } from "@/lib/types";
import { StatusPill } from "./ui/StatusPill";

export function RecallsPanel({ info }: { info: RecallInfo }) {
  return (
    <section className="card-shadow rounded-[14px] border border-line bg-surface p-7">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Official data</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Open recalls</h2>
      <p className="mt-1 text-[13px] text-ink-soft">{info.source}</p>

      {!info.available ? (
        <p className="mt-5 rounded-[10px] border border-dashed border-line-strong bg-paper px-5 py-5 text-[13.5px] text-ink-soft">
          The recall database could not be reached right now ({info.error}). Try again later; nothing is assumed about this vehicle.
        </p>
      ) : info.count === 0 ? (
        <p className="mt-5 flex items-center gap-3 text-[14px] text-ink">
          <StatusPill status="ok">None</StatusPill> No open recall is registered for this plate.
        </p>
      ) : (
        <ul className="mt-5 divide-y divide-line">
          {info.items.map((r, i) => (
            <li key={`${r.recall_id}-${i}`} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[14px] font-medium text-ink">{r.category}</p>
                <StatusPill status="critical">Open recall</StatusPill>
              </div>
              <p className="text-[12px] text-ink-soft">
                {r.type} &middot; opened {r.opened ?? "—"} &middot; recall no. {r.recall_id}
              </p>
              {r.description_he && (
                <p dir="rtl" className="mt-1 text-[13px] leading-relaxed text-ink-soft">
                  {r.description_he}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 border-t border-line pt-3 text-[12px] text-ink-soft">
        A recall is a fact published by the authority, not a prediction. Contact the importer or a dealer to have it performed free of charge.
      </p>
    </section>
  );
}
