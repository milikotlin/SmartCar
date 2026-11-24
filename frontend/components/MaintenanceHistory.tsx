"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";
import { useFmt } from "@/lib/format";
import { getWriteKey, setWriteKey } from "@/lib/writeKey";
import { addInspection, addMaintenance, ApiError } from "@/lib/api";
import type { HistoryInfo, InspectionRecord, MaintenanceRecord } from "@/lib/types";
import { CardHeader, Tag } from "./ui/StatusPill";

const CATEGORIES = ["oil", "brakes", "brake_fluid", "tires", "coolant", "battery", "filters", "other"] as const;
const DEFECTS = ["brakes", "electrical", "engine", "other"] as const;
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
  const t = useTranslations("log");
  const tError = useTranslations("errors");
  const { num, km } = useFmt();
  const [tab, setTab] = useState<"maintenance" | "inspection">("maintenance");
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => (typeof window === "undefined" ? "" : getWriteKey()));

  function changeKey(value: string) {
    setKey(value);
    setWriteKey(value);
  }

  const category = (c: string) => ((CATEGORIES as readonly string[]).includes(c) ? t(`categories.${c as (typeof CATEGORIES)[number]}`) : c);

  function requireKey(): boolean {
    if (key.trim()) return true;
    setMessage({ kind: "error", text: t("keyFirst") });
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
      setMessage({ kind: "ok", text: t("saved") });
      onChanged();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? tError(err.code) : t("couldNotSave") });
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
      setMessage({ kind: "ok", text: t("saved") });
      onChanged();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? tError(err.code) : t("couldNotSave") });
    } finally {
      setBusy(false);
    }
  }

  const submitButton = (
    <button disabled={busy} type="submit" className="col-span-2 min-h-14 rounded-xl bg-accent px-5 text-[16px] font-bold text-accent-ink shadow-sm transition-[filter] hover:brightness-110 disabled:opacity-60 max-[640px]:col-span-1">
      {busy ? t("saving") : t("save")}
    </button>
  );

  return (
    <section className="card-shadow rounded-2xl border border-line bg-surface p-6" data-testid="service-log">
      <CardHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        right={
          <>
            <Tag>{t("manual")}</Tag>
            <Tag>{t("counts", { services: history.maintenance_records, inspections: history.inspections })}</Tag>
            {history.history_used_by_model && <Tag tone="accent">{t("usedByModel")}</Tag>}
          </>
        }
      />

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {[t("date"), t("km"), t("description"), t("cost")].map((c) => (
                <th key={c} className="border-b border-line py-2 pe-3 text-start text-[11px] font-bold uppercase tracking-wider text-ink-faint">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {maintenance.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-5 text-center text-[13.5px] font-medium text-ink-faint">
                  {t("empty")}
                </td>
              </tr>
            ) : (
              maintenance.map((r) => (
                <tr key={r.record_id} className="border-b border-line last:border-b-0">
                  <td className="py-2 pe-3 font-mono text-[13px] text-ink">{r.service_date}</td>
                  <td className="py-2 pe-3 font-mono text-[13px] text-ink">{num(r.mileage_at_service)}</td>
                  <td className="py-2 pe-3 text-[13px] text-ink">
                    {r.description.startsWith("[DEMO]") && <span className="me-1.5 rounded border border-current px-1 py-0.5 font-mono text-[10px] font-bold text-warn">{t("demo")}</span>}
                    <bdi>{r.description.replace(/^\[DEMO\]\s*/, "")}</bdi>
                    {r.maintenance_category && <span className="ms-1.5 text-ink-faint">· {category(r.maintenance_category)}</span>}
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
            const defects = DEFECTS.filter((d) => i[`${d}_defect`]).map((d) => t(`defectsShort.${d}`)).join(", ");
            return (
              <Tag key={i.inspection_id} tone={defects ? "warn" : "neutral"}>
                {t("inspection", { date: i.inspection_date })}
                {i.odometer_km ? ` · ${km(i.odometer_km)}` : ""} · {defects || t("noDefect")}
              </Tag>
            );
          })}
        </div>
      )}
      {history.note && <p className="mt-2 text-[12.5px] font-semibold text-warn">{history.note}</p>}

      <div className="mt-5 border-t border-line pt-5">
        <div className="grid grid-cols-2 gap-2 max-[640px]:grid-cols-1" role="tablist">
          {(["maintenance", "inspection"] as const).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              type="button"
              onClick={() => setTab(k)}
              className={`min-h-12 rounded-xl border-2 px-4 text-[14.5px] font-bold transition-colors ${tab === k ? "border-accent bg-accent/10 text-accent" : "border-line-strong text-ink-soft hover:text-ink"}`}
            >
              {k === "maintenance" ? t("addMaintenance") : t("addInspection")}
            </button>
          ))}
        </div>

        <label className={`mt-4 block ${labelClass}`}>
          {t("key")}
          <input type="password" autoComplete="off" value={key} onChange={(e) => changeKey(e.target.value)} className={`${inputClass} block max-w-xs`} aria-label={t("key")} />
        </label>

        {tab === "maintenance" ? (
          <form onSubmit={submitMaintenance} className="mt-4 grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className={labelClass}>{t("date")}<input required name="date" type="date" className={inputClass} /></label>
            <label className={labelClass}>{t("odometer")}<input required name="km" type="number" min={0} max={1500000} className={inputClass} /></label>
            <label className={labelClass}>
              {t("category")}
              <select name="category" className={inputClass}><option value="">{t("categories.none")}</option>{CATEGORIES.map((c) => <option key={c} value={c}>{t(`categories.${c}`)}</option>)}</select>
            </label>
            <label className={labelClass}>{t("cost")}<input name="cost" type="number" min={0} step="0.01" defaultValue={0} className={inputClass} /></label>
            <label className={`col-span-2 max-[640px]:col-span-1 ${labelClass}`}>{t("description")}<input required name="description" type="text" maxLength={500} className={inputClass} placeholder={t("descriptionExample")} /></label>
            {submitButton}
          </form>
        ) : (
          <form onSubmit={submitInspection} className="mt-4 grid grid-cols-2 gap-3 max-[640px]:grid-cols-1">
            <label className={labelClass}>{t("inspectionDate")}<input required name="date" type="date" defaultValue={lastTestDate?.slice(0, 10)} className={inputClass} /></label>
            <label className={labelClass}>{t("odometer")}<input name="km" type="number" min={0} max={1500000} className={inputClass} placeholder={t("optional")} /></label>
            <fieldset className="col-span-2 max-[640px]:col-span-1">
              <legend className={labelClass}>{t("defectsFound")}</legend>
              <div className="mt-1 grid grid-cols-4 gap-2 max-[640px]:grid-cols-2">
                {DEFECTS.map((n) => (
                  <label key={n} className="flex min-h-12 cursor-pointer items-center gap-2 rounded-lg border-2 border-line-strong px-3 text-[14px] font-semibold text-ink has-[:checked]:border-critical has-[:checked]:text-critical">
                    <input type="checkbox" name={n} className="h-4 w-4 accent-critical" /> {t(`defects.${n}`)}
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
