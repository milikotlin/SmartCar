"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { parseMileage, type MileageMode } from "@/lib/mileage";
import type { MileageInfo, VehicleProfile } from "@/lib/types";

function SpecRow({ label, value, tag }: { label: string; value: ReactNode; tag?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <dt className="text-[13px] text-ink-soft">
        {label}
        {tag && (
          <span className="ml-2 inline-block whitespace-nowrap rounded border border-current px-1.5 py-0.5 align-[1px] font-mono text-[10px] tracking-wide text-accent">
            {tag}
          </span>
        )}
      </dt>
      <dd className="shrink-0 whitespace-nowrap text-right font-medium text-ink">{value}</dd>
    </div>
  );
}

const km = (n: number) => `${n.toLocaleString("en-US")} km`;

function Model1Inputs({ mileage }: { mileage: MileageInfo }) {
  const i = mileage.model_inputs ?? {};
  if (!Object.keys(i).length) return null;
  const official = String(i.engine_and_transmission_source ?? "");
  const filled = "not in the official table: filled from similar cars (KNN, K=5)";
  const engine = i.engine_cc ? `${Number(i.engine_cc).toLocaleString("en-US")} cc` : filled;
  const gearbox = i.automatic === null || i.automatic === undefined ? filled : Number(i.automatic) >= 0.5 ? "Automatic" : "Manual";
  const owners = i.owner_type && i.owner_type !== "Unknown" ? String(i.owner_type) : "Unknown (not in the ownership history)";
  const [make, model] = String(i.make_model ?? "|").split("|");
  return (
    <details className="mt-2 text-[12px] text-ink-soft" data-testid="model1-inputs">
      <summary className="cursor-pointer font-medium text-ink">What Model 1 used</summary>
      <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-x-3 gap-y-1">
        <dt>Age, fuel</dt>
        <dd className="text-right text-ink">{String(i.age)} years, {String(i.fuel).replace("lpg_cng", "LPG/CNG")} <span className="text-ink-faint">(registry)</span></dd>
        <dt>Make and model</dt>
        <dd className="text-right capitalize text-ink">{make} {model} <span className="normal-case text-ink-faint">(registry)</span></dd>
        <dt>Engine size</dt>
        <dd className="text-right text-ink">{engine}</dd>
        <dt>Transmission</dt>
        <dd className="text-right text-ink">{gearbox}</dd>
        <dt>Number of owners</dt>
        <dd className="text-right text-ink">{owners}</dd>
        {mileage.model_raw_km !== null && (
          <>
            <dt>Model output before calibration</dt>
            <dd className="text-right font-mono text-ink">{km(mileage.model_raw_km)}</dd>
          </>
        )}
      </dl>
      <p className="mt-1.5 text-ink-faint">Engine size and transmission: {official || "official model table"}. Owners: official ownership history of the Ministry of Transport.</p>
    </details>
  );
}
const mono = (children: ReactNode) => <span className="font-mono text-[13.5px]">{children}</span>;

interface Props {
  vehicle: VehicleProfile;
  mileage: MileageInfo;
  mode: MileageMode;
  onModeChange: (mode: MileageMode) => void;
  onApply: (km: number) => void;
  refreshing: boolean;
}

export function VehicleSpecCard({ vehicle, mileage, mode, onModeChange, onApply, refreshing }: Props) {
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

  return (
    <article className="card-shadow flex flex-col gap-6 rounded-[14px] border border-line bg-surface p-7">
      <div>
        <span className="inline-flex items-center gap-2 rounded-md border-[1.5px] border-line-strong px-3 py-1.5 font-mono text-[15px] font-semibold tracking-[0.12em] text-ink">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" />
          {vehicle.license_plate}
        </span>
        <h1 className="mt-3 text-balance text-2xl font-bold tracking-tight text-ink">
          {vehicle.make} {vehicle.model}
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          {vehicle.manufacture_year} &middot; {vehicle.fuel_type} &middot; {vehicle.ownership}
        </p>
      </div>

      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Official registry data &middot; Ministry of Transport</p>
        <dl className="border-t border-line">
          <SpecRow label="Manufacture year" value={mono(vehicle.manufacture_year)} />
          <SpecRow label="Fuel type" value={vehicle.fuel_type} />
          <SpecRow label="Ownership" value={vehicle.ownership} />
          <SpecRow label="Color" value={vehicle.color ?? "Not reported"} />
          <SpecRow label="Last annual test (date)" value={mono(vehicle.last_test_date ?? "—")} />
          <SpecRow label="License valid until" value={mono(vehicle.license_valid_until ?? "—")} />
        </dl>
        <p className="mt-1 text-[11.5px] text-ink-faint">The registry publishes the date of the last annual test, not its result.</p>
      </div>

      <section aria-label="Mileage" data-testid="mileage-section" aria-busy={refreshing}>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Mileage</p>

        <div role="radiogroup" aria-label="How do you want to set the mileage?" className="grid gap-2">
          <label
            className={`flex cursor-pointer items-start gap-2.5 rounded-[10px] border px-3.5 py-2.5 text-[13px] ${mode === "reported" ? "border-accent bg-paper" : "border-line"}`}
          >
            <input type="radio" name="mileage-mode" value="reported" checked={mode === "reported"} onChange={() => choose("reported")} className="mt-0.5 accent-accent" />
            <span className="font-medium text-ink">I know my car&apos;s mileage</span>
          </label>
          <label
            className={`flex cursor-pointer items-start gap-2.5 rounded-[10px] border px-3.5 py-2.5 text-[13px] ${mode === "estimate" ? "border-accent bg-paper" : "border-line"}`}
          >
            <input type="radio" name="mileage-mode" value="estimate" checked={mode === "estimate"} onChange={() => choose("estimate")} className="mt-0.5 accent-accent" />
            <span className="font-medium text-ink">I don&apos;t know my car&apos;s mileage</span>
          </label>
        </div>

        {refreshing && (
          <p role="status" data-testid="mileage-updating" className="mt-3 text-[12px] font-medium text-accent">
            Updating the results&hellip;
          </p>
        )}

        <div className={`mt-3 ${refreshing ? "opacity-50" : ""}`}>
          {mode === "reported" ? (
            <>
              <form onSubmit={submit} noValidate className="flex flex-wrap items-end gap-2.5">
                <label className="min-w-[180px] flex-1 text-[12px] text-ink-soft">
                  Enter your current mileage (km)
                  <input
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
                    placeholder="For example 123456"
                    className="mt-1 w-full rounded-md border border-line-strong bg-paper px-2.5 py-2 text-[13px] text-ink outline-none focus:border-accent"
                  />
                </label>
                <button type="submit" className="rounded-md border border-accent px-4 py-2 text-[13px] font-semibold text-accent">
                  Use This Mileage
                </button>
              </form>
              {error && (
                <p id="mileage-error" role="alert" className="mt-2 text-[12.5px] text-critical">
                  {error}
                </p>
              )}

              {reported ? (
                <div className="mt-3" data-testid="user-reported">
                  <dl className="border-t border-line">
                    <SpecRow label="User-Reported Mileage" tag="USER-REPORTED" value={mono(km(mileage.primary_km))} />
                    {mileage.measured_km !== null && (
                      <SpecRow label={`Recorded odometer (${mileage.measured_as_of ?? "on file"})`} tag="RECORD" value={mono(km(mileage.measured_km))} />
                    )}
                  </dl>
                  <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                    Reported by you for this view. It has not been verified or officially confirmed, and it is not saved.
                  </p>
                  {mileage.user_reported_note && (
                    <p data-testid="user-reported-note" className="mt-1.5 text-[12px] leading-relaxed text-ink-soft">
                      <strong className="font-semibold text-ink">Risk models:</strong> {mileage.user_reported_note}
                    </p>
                  )}
                </div>
              ) : (
                <p className="mt-3 text-[12px] leading-relaxed text-ink-soft" data-testid="no-mileage-yet">
                  No mileage entered yet. Enter a value and press &ldquo;Use This Mileage&rdquo;, or choose the automatic estimate.
                </p>
              )}
            </>
          ) : (
            <div data-testid="ai-estimate">
              <dl className="border-t border-line">
                {mileage.measured_km !== null && (
                  <SpecRow label={`Recorded odometer (${mileage.measured_as_of ?? "on file"})`} tag="RECORD" value={mono(km(mileage.measured_km))} />
                )}
                <SpecRow label={mileage.measured_km !== null ? "AI-Estimated Mileage (for comparison)" : "AI-Estimated Mileage"} tag="ML" value={mono(km(mileage.estimated_km))} />
                <SpecRow label="Indicative range (80%)" value={<span className="font-mono text-[13px] text-ink-soft">{mileage.estimated_low_km.toLocaleString("en-US")} &ndash; {mileage.estimated_high_km.toLocaleString("en-US")} km</span>} />
              </dl>
              {mileage.estimate_reliability === "low" && (
                <p role="note" data-testid="low-reliability" className="mt-2 rounded-md border border-warn bg-paper px-3 py-2 text-[12px] leading-relaxed text-ink">
                  <strong className="font-semibold text-warn">Low reliability.</strong> {(mileage.estimate_reliability_reason ?? "").replace(/^./, (c) => c.toUpperCase())}. Treat this figure as a rough guide only.
                </p>
              )}
              <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">
                Model 1 (an XGBoost regression, chosen among Linear, Ridge, Random Forest and XGBoost) estimates this from the vehicle&apos;s characteristics. {mileage.label}
              </p>
              <Model1Inputs mileage={mileage} />
            </div>
          )}
          {mileage.notes.length > 0 && mode === "estimate" && (
            <ul className="mt-1.5 list-disc pl-5 text-[12px] text-ink-faint">
              {mileage.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </article>
  );
}
