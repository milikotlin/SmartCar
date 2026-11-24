"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { parseMileage, type MileageMode } from "@/lib/mileage";
import type { MileageInfo, VehicleProfile } from "@/lib/types";
import { StatusPill, Tag } from "./ui/StatusPill";

const km = (n: number) => `${n.toLocaleString("en-US")} km`;

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-bold uppercase tracking-wider text-ink-faint">{label}</dt>
      <dd className="mt-0.5 truncate text-[15px] font-semibold text-ink">{value}</dd>
    </div>
  );
}

function reliabilityTag(reason: string | null): string {
  const r = (reason ?? "").toLowerCase();
  if (r.includes("official average")) return "Official average shown";
  if (r.includes("electric")) return "No Israeli EV statistics";
  if (r.includes("too few")) return "Sparse training data";
  return "Outside the data";
}

function Kpi({ value, tag }: { value: number; tag: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <p className="font-mono text-[34px] font-bold leading-none tracking-tight text-ink">{km(value)}</p>
      {tag}
    </div>
  );
}

function Model1Inputs({ mileage }: { mileage: MileageInfo }) {
  const i = mileage.model_inputs ?? {};
  if (!Object.keys(i).length) return null;
  const imputed = "Imputed (KNN, K=5)";
  const engine = i.engine_cc ? `${Number(i.engine_cc).toLocaleString("en-US")} cc` : imputed;
  const gearbox = i.automatic === null || i.automatic === undefined ? imputed : Number(i.automatic) >= 0.5 ? "Automatic" : "Manual";
  const owners = i.owner_type && i.owner_type !== "Unknown" ? String(i.owner_type) : "Unknown";
  const [make, model] = String(i.make_model ?? "|").split("|");
  const rows: [string, ReactNode][] = [
    ["Age", `${String(i.age)} y`],
    ["Fuel", String(i.fuel).replace("lpg_cng", "LPG/CNG")],
    ["Make / model", <span key="mm" className="capitalize">{`${make} ${model}`}</span>],
    ["Engine CC", engine],
    ["Transmission", gearbox],
    ["Owners", owners],
    ["Pre-calibration output", mileage.model_raw_km !== null ? km(mileage.model_raw_km) : "—"],
    ["Calibration", "CBS 1923 · age × ownership"],
  ];
  return (
    <details className="group mt-4 rounded-xl border border-line" data-testid="model1-inputs">
      <summary className="flex min-h-11 cursor-pointer items-center justify-between px-4 text-[13.5px] font-bold text-ink">
        Model 1 Inputs &amp; Breakdown
        <span className="text-ink-faint transition-transform group-open:rotate-180">▾</span>
      </summary>
      <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-x-3 gap-y-1.5 border-t border-line px-4 py-3 text-[13px]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-soft">{k}</dt>
            <dd className="text-right font-mono font-semibold text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {mileage.notes.length > 0 && (
        <ul className="border-t border-line px-4 py-2.5 text-[12px] text-ink-faint">
          {mileage.notes.map((n) => (
            <li key={n}>· {n}</li>
          ))}
        </ul>
      )}
    </details>
  );
}

interface Props {
  vehicle: VehicleProfile;
  mileage: MileageInfo;
  mode: MileageMode;
  onModeChange: (mode: MileageMode) => void;
  onApply: (km: number) => void;
  refreshing: boolean;
  /** km_source of the Model 2 (PDF) input: shows whether the typed value reached it */
  model2KmSource?: string;
}

export function VehicleSpecCard({ vehicle, mileage, mode, onModeChange, onApply, refreshing, model2KmSource }: Props) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const reported = mileage.primary_source === "user_reported";

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = parseMileage(draft);
    if (!parsed.ok) {
      setError(parsed.message);
      return;
    }
    setError(null);
    onApply(parsed.km);
  }

  function choose(next: MileageMode) {
    if (next === mode) return;
    setError(null);
    if (next === "estimate") setDraft("");
    onModeChange(next);
  }

  const segment = (m: MileageMode, label: string) => (
    <button
      type="button"
      role="radio"
      aria-checked={mode === m}
      data-mode={m}
      onClick={() => choose(m)}
      className={`min-h-12 rounded-lg px-3 text-[14px] font-bold transition-colors ${mode === m ? "bg-accent text-accent-ink shadow-sm" : "text-ink-soft hover:text-ink"}`}
    >
      {label}
    </button>
  );

  return (
    <article className="card-shadow flex flex-col gap-5 rounded-2xl border border-line bg-surface p-6">
      <div>
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-2 rounded-lg border-2 border-ink px-3 py-1 font-mono text-[17px] font-bold tracking-[0.14em] text-ink">
            {vehicle.license_plate}
          </span>
          <Tag>Ministry of Transport</Tag>
        </div>
        <h1 className="mt-3 text-[26px] font-bold leading-tight tracking-tight text-ink">
          {vehicle.make} {vehicle.model}
        </h1>
      </div>

      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 border-y border-line py-4">
        <Field label="Year" value={vehicle.manufacture_year} />
        <Field label="Fuel" value={vehicle.fuel_type} />
        <Field label="Ownership" value={vehicle.ownership} />
        <Field label="Color" value={vehicle.color ?? "—"} />
        <Field label="Last test" value={<span className="font-mono">{vehicle.last_test_date?.slice(0, 10) ?? "—"}</span>} />
        <Field label="License valid" value={<span className="font-mono">{vehicle.license_valid_until?.slice(0, 10) ?? "—"}</span>} />
      </dl>

      <section aria-label="Mileage" data-testid="mileage-section" aria-busy={refreshing}>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11.5px] font-bold uppercase tracking-[0.12em] text-ink-faint">Model 1 · Mileage</p>
          {refreshing && (
            <span role="status" data-testid="mileage-updating" className="text-[12px] font-bold text-accent">
              Updating…
            </span>
          )}
        </div>

        <div role="radiogroup" aria-label="Mileage source" className="grid grid-cols-2 gap-1 rounded-xl bg-chip p-1">
          {segment("estimate", "AI Estimated Mileage")}
          {segment("reported", "Enter Known Mileage")}
        </div>

        <div className={`mt-4 ${refreshing ? "opacity-50" : ""}`}>
          {mode === "estimate" ? (
            <div data-testid="ai-estimate">
              {mileage.measured_km !== null ? (
                <>
                  <Kpi value={mileage.measured_km} tag={<Tag tone="accent">Service record</Tag>} />
                  <p className="mt-2 text-[13px] text-ink-soft">
                    Recorded {mileage.measured_as_of} · AI estimate <span className="font-mono font-semibold text-ink">{km(mileage.estimated_km)}</span>
                  </p>
                </>
              ) : (
                <Kpi value={mileage.estimated_km} tag={<Tag tone="accent">XGBoost Regressor</Tag>} />
              )}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 rounded-lg bg-chip px-3 py-2 text-[13px]">
                <span className="font-semibold text-ink-soft">80% Confidence Interval</span>
                <span className="font-mono font-bold text-ink">
                  {mileage.estimated_low_km.toLocaleString("en-US")} – {mileage.estimated_high_km.toLocaleString("en-US")} km
                </span>
              </div>
              {mileage.estimate_reliability === "low" && (
                <div role="note" data-testid="low-reliability" className="mt-2 flex flex-wrap items-center gap-2" title={mileage.estimate_reliability_reason ?? undefined}>
                  <StatusPill status="warn">Low reliability</StatusPill>
                  <Tag tone="warn">{reliabilityTag(mileage.estimate_reliability_reason)}</Tag>
                </div>
              )}
              <Model1Inputs mileage={mileage} />
            </div>
          ) : (
            <>
              <form onSubmit={submit} noValidate className="flex gap-2">
                <label className="sr-only" htmlFor="known-mileage">
                  Enter your current mileage (km)
                </label>
                <input
                  id="known-mileage"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  value={draft}
                  onChange={(e) => {
                    setDraft(e.target.value);
                    setError(null);
                  }}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? "mileage-error" : undefined}
                  placeholder="Current km, e.g. 123456"
                  className="h-12 min-w-0 flex-1 rounded-lg border-2 border-line-strong bg-paper px-3 font-mono text-[17px] font-semibold text-ink outline-none placeholder:font-sans placeholder:text-[14px] placeholder:font-normal focus:border-accent"
                />
                <button type="submit" className="h-12 whitespace-nowrap rounded-lg bg-accent px-5 text-[14px] font-bold text-accent-ink hover:brightness-110">
                  Use Mileage
                </button>
              </form>
              {error && (
                <p id="mileage-error" role="alert" className="mt-2 text-[13px] font-semibold text-critical">
                  {error}
                </p>
              )}
              {reported ? (
                <div className="mt-4" data-testid="user-reported">
                  <Kpi value={mileage.primary_km} tag={<Tag tone="accent">User-reported</Tag>} />
                  <div className="mt-3 flex flex-wrap gap-2" data-testid="user-reported-note" title={mileage.user_reported_note ?? undefined}>
                    <Tag>Not verified · not saved</Tag>
                    <Tag tone={model2KmSource === "user_reported" ? "accent" : "warn"}>Model 2 input {model2KmSource === "user_reported" ? "✓" : "✗"}</Tag>
                    <Tag tone={mileage.user_reported_used_by_model2 ? "accent" : "warn"}>UK model input {mileage.user_reported_used_by_model2 ? "✓" : "✗"}</Tag>
                  </div>
                  {mileage.measured_km !== null && (
                    <p className="mt-2 text-[13px] text-ink-soft">
                      Service record <span className="font-mono font-semibold text-ink">{km(mileage.measured_km)}</span> · {mileage.measured_as_of}
                    </p>
                  )}
                </div>
              ) : (
                <p className="mt-4 text-[13px] font-medium text-ink-faint" data-testid="no-mileage-yet">
                  No mileage entered
                </p>
              )}
            </>
          )}
        </div>
      </section>
    </article>
  );
}
