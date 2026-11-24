"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent, type ReactNode } from "react";
import { useFmt } from "@/lib/format";
import { MAX_MILEAGE_KM, parseMileage, type MileageErrorCode, type MileageMode } from "@/lib/mileage";
import type { MileageInfo, VehicleProfile } from "@/lib/types";
import { StatusPill, Tag } from "./ui/StatusPill";

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-bold uppercase tracking-wider text-ink-faint">{label}</dt>
      <dd className="mt-0.5 truncate text-[15px] font-semibold text-ink">{value}</dd>
    </div>
  );
}

/** Backend reason codes -> short badges. */
const RELIABILITY_TAG = { m1_official_average: "officialAverage", m1_old_for_fuel: "officialAverage", m1_no_ev_statistics: "noEv", m1_too_few: "sparse" } as const;
const reliabilityTag = (code: string | null) => (code && code in RELIABILITY_TAG ? RELIABILITY_TAG[code as keyof typeof RELIABILITY_TAG] : ("outside" as const));

function Kpi({ value, tag }: { value: number; tag: ReactNode }) {
  const { km } = useFmt();
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <p className="font-mono text-[34px] font-bold leading-none tracking-tight text-ink">{km(value)}</p>
      {tag}
    </div>
  );
}

function Model1Inputs({ mileage }: { mileage: MileageInfo }) {
  const t = useTranslations();
  const { km, num } = useFmt();
  const i = mileage.model_inputs ?? {};
  if (!Object.keys(i).length) return null;
  const imputed = t("model1.imputed");
  const engine = i.engine_cc ? t("units.cc", { value: num(Number(i.engine_cc)) }) : imputed;
  const gearbox = i.automatic === null || i.automatic === undefined ? imputed : Number(i.automatic) >= 0.5 ? t("model1.automatic") : t("model1.manual");
  const owner = String(i.owner_type ?? "Unknown").split(" ")[0] as "First" | "Second" | "Third" | "Fourth" | "Unknown"; // "Fourth & Above" -> Fourth
  const fuel = String(i.fuel) as "petrol" | "diesel" | "hybrid" | "electric" | "lpg_cng" | "unknown";
  const [make, model] = String(i.make_model ?? "|").split("|");
  const rows: [string, ReactNode][] = [
    [t("model1.age"), t("units.years", { value: String(i.age) })],
    [t("model1.fuel"), t(`fuel.${fuel}`)],
    [t("model1.makeModel"), <bdi key="mm" className="capitalize">{`${make} ${model}`}</bdi>],
    [t("model1.engine"), engine],
    [t("model1.transmission"), gearbox],
    [t("model1.owners"), t(`model1.ownerType.${owner}`)],
    [t("model1.preCalibration"), mileage.model_raw_km !== null ? km(mileage.model_raw_km) : "—"],
    [t("model1.calibration"), t("model1.calibrationValue")],
  ];
  return (
    <details className="group mt-4 rounded-xl border border-line" data-testid="model1-inputs">
      <summary className="flex min-h-11 cursor-pointer items-center justify-between px-4 text-[13.5px] font-bold text-ink">
        {t("model1.title")}
        <span className="text-ink-faint transition-transform group-open:rotate-180">▾</span>
      </summary>
      <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-x-3 gap-y-1.5 border-t border-line px-4 py-3 text-[13px]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-soft">{k}</dt>
            <dd className="text-end font-mono font-semibold text-ink">{v}</dd>
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
  const t = useTranslations();
  const { km, num } = useFmt();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<MileageErrorCode | null>(null);
  const strong = (chunks: ReactNode) => <bdi className="font-mono font-semibold text-ink">{chunks}</bdi>;
  const reported = mileage.primary_source === "user_reported";

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = parseMileage(draft);
    if (!parsed.ok) {
      setError(parsed.code);
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
          <span dir="ltr" className="inline-flex items-center gap-2 rounded-lg border-2 border-ink px-3 py-1 font-mono text-[17px] font-bold tracking-[0.14em] text-ink">
            {vehicle.license_plate}
          </span>
          <Tag>{t("vehicle.source")}</Tag>
        </div>
        <h1 className="mt-3 text-[26px] font-bold leading-tight tracking-tight text-ink">
          {vehicle.make} <bdi>{vehicle.model}</bdi>
        </h1>
      </div>

      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 border-y border-line py-4">
        <Field label={t("vehicle.year")} value={vehicle.manufacture_year} />
        <Field label={t("vehicle.fuel")} value={vehicle.fuel_type} />
        <Field label={t("vehicle.ownership")} value={vehicle.ownership} />
        <Field label={t("vehicle.color")} value={vehicle.color ?? "—"} />
        <Field label={t("vehicle.lastTest")} value={<span className="font-mono">{vehicle.last_test_date?.slice(0, 10) ?? "—"}</span>} />
        <Field label={t("vehicle.licenseValid")} value={<span className="font-mono">{vehicle.license_valid_until?.slice(0, 10) ?? "—"}</span>} />
      </dl>

      <section aria-label={t("mileage.section")} data-testid="mileage-section" aria-busy={refreshing}>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11.5px] font-bold uppercase tracking-[0.12em] text-ink-faint">{t("mileage.eyebrow")}</p>
          {refreshing && (
            <span role="status" data-testid="mileage-updating" className="text-[12px] font-bold text-accent">
              {t("mileage.updating")}
            </span>
          )}
        </div>

        <div role="radiogroup" aria-label={t("mileage.source")} className="grid grid-cols-2 gap-1 rounded-xl bg-chip p-1">
          {segment("estimate", t("mileage.estimateTab"))}
          {segment("reported", t("mileage.knownTab"))}
        </div>

        <div className={`mt-4 ${refreshing ? "opacity-50" : ""}`}>
          {mode === "estimate" ? (
            <div data-testid="ai-estimate">
              {mileage.measured_km !== null ? (
                <>
                  <Kpi value={mileage.measured_km} tag={<Tag tone="accent">{t("mileage.serviceRecord")}</Tag>} />
                  <p className="mt-2 text-[13px] text-ink-soft">
                    {t.rich("mileage.recorded", { date: mileage.measured_as_of ?? "", km: km(mileage.estimated_km), b: strong })}
                  </p>
                </>
              ) : (
                <Kpi value={mileage.estimated_km} tag={<Tag tone="accent">{t("mileage.regressor")}</Tag>} />
              )}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 rounded-lg bg-chip px-3 py-2 text-[13px]">
                <span className="font-semibold text-ink-soft">{t("mileage.interval")}</span>
                <span className="font-mono font-bold text-ink">
                  {t("units.km", { value: `${num(mileage.estimated_low_km)} – ${num(mileage.estimated_high_km)}` })}
                </span>
              </div>
              {mileage.estimate_reliability === "low" && (
                <div role="note" data-testid="low-reliability" className="mt-2 flex flex-wrap items-center gap-2" title={mileage.estimate_reliability_reason ?? undefined}>
                  <StatusPill status="warn">{t("mileage.lowReliability")}</StatusPill>
                  <Tag tone="warn">{t(`mileage.reliability.${reliabilityTag(mileage.estimate_reliability_code)}`)}</Tag>
                </div>
              )}
              <Model1Inputs mileage={mileage} />
            </div>
          ) : (
            <>
              <form onSubmit={submit} noValidate className="flex gap-2">
                <label className="sr-only" htmlFor="known-mileage">
                  {t("mileage.inputLabel")}
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
                  placeholder={t("mileage.placeholder")}
                  className="h-12 min-w-0 flex-1 rounded-lg border-2 border-line-strong bg-paper px-3 font-mono text-[17px] font-semibold text-ink outline-none placeholder:font-sans placeholder:text-[14px] placeholder:font-normal focus:border-accent"
                />
                <button type="submit" className="h-12 whitespace-nowrap rounded-lg bg-accent px-5 text-[14px] font-bold text-accent-ink hover:brightness-110">
                  {t("mileage.use")}
                </button>
              </form>
              {error && (
                <p id="mileage-error" role="alert" className="mt-2 text-[13px] font-semibold text-critical">
                  {t(`mileage.errors.${error}`, { max: num(MAX_MILEAGE_KM) })}
                </p>
              )}
              {reported ? (
                <div className="mt-4" data-testid="user-reported">
                  <Kpi value={mileage.primary_km} tag={<Tag tone="accent">{t("mileage.userReported")}</Tag>} />
                  <div className="mt-3 flex flex-wrap gap-2" data-testid="user-reported-note" title={mileage.user_reported_note ?? undefined}>
                    <Tag>{t("mileage.notVerified")}</Tag>
                    <Tag tone={model2KmSource === "user_reported" ? "accent" : "warn"}>{t("mileage.model2Input", { mark: model2KmSource === "user_reported" ? "✓" : "✗" })}</Tag>
                    <Tag tone={mileage.user_reported_used_by_model2 ? "accent" : "warn"}>{t("mileage.ukInput", { mark: mileage.user_reported_used_by_model2 ? "✓" : "✗" })}</Tag>
                  </div>
                  {mileage.measured_km !== null && (
                    <p className="mt-2 text-[13px] text-ink-soft">
                      {t.rich("mileage.serviceRecordOn", { km: km(mileage.measured_km), date: mileage.measured_as_of ?? "", b: strong })}
                    </p>
                  )}
                </div>
              ) : (
                <p className="mt-4 text-[13px] font-medium text-ink-faint" data-testid="no-mileage-yet">
                  {t("mileage.none")}
                </p>
              )}
            </>
          )}
        </div>
      </section>
    </article>
  );
}
