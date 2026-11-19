"use client";

import { useState, type FormEvent } from "react";
import { getWriteKey, setWriteKey } from "@/lib/writeKey";
import { addInspection, addMaintenance } from "@/lib/api";
import type { HistoryInfo, InspectionRecord, MaintenanceRecord } from "@/lib/types";

const COLUMNS = ["Date", "Mileage", "Description", "Category", "Cost"];
const CATEGORIES = ["", "oil", "brakes", "brake_fluid", "tires", "coolant", "battery", "filters", "other"];
const inputClass = "w-full rounded-md border border-line-strong bg-paper px-2.5 py-2 text-[13px] text-ink outline-none focus:border-accent";

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
    setMessage({ kind: "error", text: "Enter the workshop key first: only authorised workshops can add records." });
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
      setMessage({ kind: "ok", text: "Maintenance record saved." });
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
      setMessage({ kind: "ok", text: "Inspection result saved; the risk panel was refreshed." });
      onChanged();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card-shadow rounded-[14px] border border-line bg-surface py-2">
      <div className="px-7 pt-6">
        <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Service log</p>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Maintenance and inspection history</h2>
        <p className="mt-1 text-[13px] text-ink-soft">
          Manual records, not official data &middot; {history.maintenance_records} maintenance, {history.inspections} inspection result(s)
          {history.history_used_by_model ? " · the last inspection result is used by the risk model" : ""}.
        </p>
        {history.note && <p className="mt-1 text-[12px] text-warn">{history.note}</p>}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c} className="border-b border-line px-7 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {maintenance.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-7 py-8 text-center text-[13.5px] text-ink-soft">
                  No maintenance records for this vehicle yet.
                </td>
              </tr>
            ) : (
              maintenance.map((r) => (
                <tr key={r.record_id} className="border-b border-line last:border-b-0">
                  <td className="px-7 py-2.5 font-mono text-[13px]">{r.service_date}</td>
                  <td className="px-7 py-2.5 font-mono text-[13px]">{r.mileage_at_service.toLocaleString("en-US")} km</td>
                  <td className="px-7 py-2.5 text-[13px]">
                    {r.description.startsWith("[DEMO]") && <span className="mr-1.5 rounded border border-current px-1 py-0.5 font-mono text-[10px] text-warn">DEMO</span>}
                    {r.description.replace(/^\[DEMO\]\s*/, "")}
                  </td>
                  <td className="px-7 py-2.5 text-[13px] text-ink-soft">{r.maintenance_category ?? "—"}</td>
                  <td className="px-7 py-2.5 font-mono text-[13px]">{Number(r.total_cost).toFixed(2)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {inspections.length > 0 && (
        <div className="px-7 pt-4">
          <p className="text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Annual inspection results on file</p>
          <ul className="mt-1.5 space-y-1 text-[13px] text-ink-soft">
            {inspections.map((i) => (
              <li key={i.inspection_id}>
                <span className="font-mono text-ink">{i.inspection_date}</span>
                {i.odometer_km ? ` · ${i.odometer_km.toLocaleString("en-US")} km` : ""} ·{" "}
                {[i.brakes_defect && "brakes", i.electrical_defect && "electrical", i.engine_defect && "engine-related", i.other_defect && "other"].filter(Boolean).join(", ") || "no defect recorded"}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 border-t border-line px-7 pb-6 pt-5">
        <label className="mb-4 block text-[12px] text-ink-soft">
          Workshop key <span className="text-ink-faint">(needed to add records; reading is open)</span>
          <input
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => changeKey(e.target.value)}
            className={`${inputClass} mt-1 block max-w-xs`}
            aria-label="Workshop key"
          />
        </label>
        <div className="mb-3 flex gap-2" role="tablist">
          {(["maintenance", "inspection"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-md border px-3 py-1.5 text-[12.5px] font-medium ${tab === t ? "border-accent text-accent" : "border-line-strong text-ink-soft"}`}
            >
              {t === "maintenance" ? "Add maintenance record" : "Add annual inspection result"}
            </button>
          ))}
        </div>

        {tab === "maintenance" ? (
          <form onSubmit={submitMaintenance} className="grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className="text-[12px] text-ink-soft">Service date<input required name="date" type="date" className={inputClass} /></label>
            <label className="text-[12px] text-ink-soft">Odometer (km)<input required name="km" type="number" min={0} max={1500000} className={inputClass} /></label>
            <label className="col-span-2 text-[12px] text-ink-soft max-[640px]:col-span-1">Description<input required name="description" type="text" maxLength={500} className={inputClass} placeholder="e.g. Replaced front brake pads" /></label>
            <label className="text-[12px] text-ink-soft">Category
              <select name="category" className={inputClass}>{CATEGORIES.map((c) => <option key={c} value={c}>{c || "(none)"}</option>)}</select>
            </label>
            <label className="text-[12px] text-ink-soft">Cost<input name="cost" type="number" min={0} step="0.01" defaultValue={0} className={inputClass} /></label>
            <button disabled={busy} type="submit" className="rounded-md bg-accent px-4 py-2 text-[13px] font-semibold text-accent-ink disabled:opacity-60">Save record</button>
          </form>
        ) : (
          <form onSubmit={submitInspection} className="grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className="text-[12px] text-ink-soft">Inspection date{lastTestDate ? ` (registry: ${lastTestDate})` : ""}<input required name="date" type="date" defaultValue={lastTestDate?.slice(0, 10)} className={inputClass} /></label>
            <label className="text-[12px] text-ink-soft">Odometer at the inspection (km, optional)<input name="km" type="number" min={0} max={1500000} className={inputClass} /></label>
            <fieldset className="col-span-2 flex flex-wrap gap-4 text-[13px] text-ink max-[640px]:col-span-1">
              <legend className="mb-1 text-[12px] text-ink-soft">Defects found, by system (as on the inspection report)</legend>
              {[["brakes", "Brakes"], ["electrical", "Electrical / lighting"], ["engine", "Engine-related (emissions, fuel, mounts)"], ["other", "Other"]].map(([n, l]) => (
                <label key={n} className="flex items-center gap-1.5"><input type="checkbox" name={n} /> {l}</label>
              ))}
            </fieldset>
            <p className="col-span-2 text-[12px] text-ink-soft max-[640px]:col-span-1">
              Only the result of the <strong>last annual inspection</strong> improves the risk estimate. A service or repair record is not equivalent and is not used as one.
            </p>
            <button disabled={busy} type="submit" className="rounded-md bg-accent px-4 py-2 text-[13px] font-semibold text-accent-ink disabled:opacity-60">Save inspection result</button>
          </form>
        )}
        {message && <p role="status" className={`mt-3 text-[12.5px] ${message.kind === "ok" ? "text-ok" : "text-critical"}`}>{message.text}</p>}
      </div>
    </section>
  );
}
