"use client";

import { useState, type FormEvent } from "react";
import { getWriteKey, setWriteKey } from "@/lib/writeKey";
import { addInspection, addMaintenance } from "@/lib/api";
import type { HistoryInfo, InspectionRecord, MaintenanceRecord } from "@/lib/types";
import { CardHeader, Tag } from "./ui/StatusPill";

const CATEGORIES = ["", "oil", "brakes", "brake_fluid", "tires", "coolant", "battery", "filters", "other"];
const inputClass = "mt-1 h-12 w-full rounded-lg border-2 border-line-strong bg-paper px-3 text-[14.5px] font-medium text-ink outline-none focus:border-accent";
const labelClass = "text-[12px] font-bold uppercase tracking-wider text-ink-faint";

interface Props {
  plate: string;
  maintenance: MaintenanceRecord[];
  inspections: InspectionRecord[];
  history: HistoryInfo;
  lastTestDate: string | null;
  onChanged: () => void;
}

export function MaintenanceHistory({ plate, maintenance, inspections, history, lastTestDate, onChanged }: Props) {
  const [tab, setTab] = useState<"maintenance" | "inspection">("maintenance");
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => (typeof window === "undefined" ? "" : getWriteKey()));

  function changeKey(value: string) {
    setKey(value);
    setWriteKey(value);
  }

  function requireKey(): boolean {
    if (key.trim()) return true;
    setMessage({ kind: "error", text: "Enter the workshop key first" });
    return false;
  }

  async function submitMaintenance(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!requireKey()) return;
    setBusy(true);
    try {
      await addMaintenance(plate, {
        service_date: String(f.get("date")),
        mileage_at_service: Number(f.get("km")),
        description: String(f.get("description")),
        maintenance_category: String(f.get("category") || "") || null,
        total_cost: Number(f.get("cost") || 0),
      }, key.trim());
      (e.target as HTMLFormElement).reset();
      setMessage({ kind: "ok", text: "Saved · risk recalculated" });
      onChanged();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  }

  async function submitInspection(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!requireKey()) return;
    setBusy(true);
    try {
      await addInspection(plate, {
        inspection_date: String(f.get("date")),
        odometer_km: f.get("km") ? Number(f.get("km")) : null,
        brakes_defect: f.get("brakes") === "on",
        electrical_defect: f.get("electrical") === "on",
        engine_defect: f.get("engine") === "on",
        other_defect: f.get("other") === "on",
      }, key.trim());
      (e.target as HTMLFormElement).reset();
      setMessage({ kind: "ok", text: "Saved · risk recalculated" });
      onChanged();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  }

  const submitButton = (
    <button disabled={busy} type="submit" className="col-span-2 min-h-14 rounded-xl bg-accent px-5 text-[16px] font-bold text-accent-ink shadow-sm transition-[filter] hover:brightness-110 disabled:opacity-60 max-[640px]:col-span-1">
      {busy ? "Saving…" : "Save & Recalculate Risk"}
    </button>
  );

  return (
    <section className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="service-log">
      <CardHeader
        eyebrow="Live demo trigger"
        title="Service Log"
        right={
          <>
            <Tag>Manual records</Tag>
            <Tag>{`${history.maintenance_records} service · ${history.inspections} inspection`}</Tag>
            {history.history_used_by_model && <Tag tone="accent">Last inspection → UK model</Tag>}
          </>
        }
      />

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {["Date", "Km", "Description", "Cost"].map((c) => (
                <th key={c} className="border-b border-line py-2 pr-3 text-left text-[11px] font-bold uppercase tracking-wider text-ink-faint">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {maintenance.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-5 text-center text-[13.5px] font-medium text-ink-faint">
                  No service records
                </td>
              </tr>
            ) : (
              maintenance.map((r) => (
                <tr key={r.record_id} className="border-b border-line last:border-b-0">
                  <td className="py-2 pr-3 font-mono text-[13px] text-ink">{r.service_date}</td>
                  <td className="py-2 pr-3 font-mono text-[13px] text-ink">{r.mileage_at_service.toLocaleString("en-US")}</td>
                  <td className="py-2 pr-3 text-[13px] text-ink">
                    {r.description.startsWith("[DEMO]") && <span className="mr-1.5 rounded border border-current px-1 py-0.5 font-mono text-[10px] font-bold text-warn">DEMO</span>}
                    {r.description.replace(/^\[DEMO\]\s*/, "")}
                    {r.maintenance_category && <span className="ml-1.5 text-ink-faint">· {r.maintenance_category}</span>}
                  </td>
                  <td className="py-2 font-mono text-[13px] text-ink">{Number(r.total_cost).toFixed(0)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {inspections.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2" data-testid="inspections-on-file">
          {inspections.map((i) => {
            const defects = [i.brakes_defect && "brakes", i.electrical_defect && "electrical", i.engine_defect && "engine", i.other_defect && "other"].filter(Boolean).join(", ");
            return (
              <Tag key={i.inspection_id} tone={defects ? "warn" : "neutral"}>
                Inspection {i.inspection_date}
                {i.odometer_km ? ` · ${i.odometer_km.toLocaleString("en-US")} km` : ""} · {defects || "no defect"}
              </Tag>
            );
          })}
        </div>
      )}
      {history.note && <p className="mt-2 text-[12.5px] font-semibold text-warn">{history.note}</p>}

      <div className="mt-5 border-t border-line pt-5">
        <div className="grid grid-cols-2 gap-2 max-[640px]:grid-cols-1" role="tablist">
          {(["maintenance", "inspection"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              type="button"
              onClick={() => setTab(t)}
              className={`min-h-12 rounded-xl border-2 px-4 text-[14.5px] font-bold transition-colors ${tab === t ? "border-accent bg-accent/10 text-accent" : "border-line-strong text-ink-soft hover:text-ink"}`}
            >
              {t === "maintenance" ? "＋ Add Maintenance Record" : "＋ Add Inspection Result"}
            </button>
          ))}
        </div>

        <label className={`mt-4 block ${labelClass}`}>
          Workshop key
          <input type="password" autoComplete="off" value={key} onChange={(e) => changeKey(e.target.value)} className={`${inputClass} block max-w-xs`} aria-label="Workshop key" />
        </label>

        {tab === "maintenance" ? (
          <form onSubmit={submitMaintenance} className="mt-4 grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className={labelClass}>Date<input required name="date" type="date" className={inputClass} /></label>
            <label className={labelClass}>Odometer (km)<input required name="km" type="number" min={0} max={1500000} className={inputClass} /></label>
            <label className={labelClass}>
              Category
              <select name="category" className={inputClass}>{CATEGORIES.map((c) => <option key={c} value={c}>{c || "(none)"}</option>)}</select>
            </label>
            <label className={labelClass}>Cost<input name="cost" type="number" min={0} step="0.01" defaultValue={0} className={inputClass} /></label>
            <label className={`col-span-2 max-[640px]:col-span-1 ${labelClass}`}>Description<input required name="description" type="text" maxLength={500} className={inputClass} placeholder="e.g. Replaced front brake pads" /></label>
            {submitButton}
          </form>
        ) : (
          <form onSubmit={submitInspection} className="mt-4 grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className={labelClass}>Inspection date<input required name="date" type="date" defaultValue={lastTestDate?.slice(0, 10)} className={inputClass} /></label>
            <label className={labelClass}>Odometer (km)<input name="km" type="number" min={0} max={1500000} className={inputClass} placeholder="optional" /></label>
            <fieldset className="col-span-2 max-[640px]:col-span-1">
              <legend className={labelClass}>Defects found</legend>
              <div className="mt-1 grid grid-cols-4 gap-2 max-[640px]:grid-cols-2">
                {[["brakes", "Brakes"], ["electrical", "Electrical"], ["engine", "Engine"], ["other", "Other"]].map(([n, l]) => (
                  <label key={n} className="flex min-h-12 cursor-pointer items-center gap-2 rounded-lg border-2 border-line-strong px-3 text-[14px] font-semibold text-ink has-[:checked]:border-critical has-[:checked]:text-critical">
                    <input type="checkbox" name={n} className="h-4 w-4 accent-critical" /> {l}
                  </label>
                ))}
              </div>
            </fieldset>
            {submitButton}
          </form>
        )}
        {message && (
          <p role="status" className={`mt-3 text-[13.5px] font-bold ${message.kind === "ok" ? "text-ok" : "text-critical"}`}>
            {message.text}
          </p>
        )}
      </div>
    </section>
  );
}
