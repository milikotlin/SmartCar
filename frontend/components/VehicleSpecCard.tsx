import type { ReactNode } from "react";
import type { MileageInfo, VehicleProfile } from "@/lib/types";

function SpecRow({ label, value, tag }: { label: string; value: ReactNode; tag?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <dt className="text-[13px] text-ink-soft">
        {label}
        {tag && (
          <span className="ml-2 rounded border border-current px-1.5 py-0.5 align-[1px] font-mono text-[10px] tracking-wide text-accent">
            {tag}
          </span>
        )}
      </dt>
      <dd className="text-right font-medium text-ink">{value}</dd>
    </div>
  );
}

const km = (n: number) => `${n.toLocaleString("en-US")} km`;

export function VehicleSpecCard({ vehicle, mileage }: { vehicle: VehicleProfile; mileage: MileageInfo }) {
  const measured = mileage.primary_source === "measured";
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
          <SpecRow label="Manufacture year" value={<span className="font-mono text-[13.5px]">{vehicle.manufacture_year}</span>} />
          <SpecRow label="Fuel type" value={vehicle.fuel_type} />
          <SpecRow label="Ownership" value={vehicle.ownership} />
          <SpecRow label="Color" value={vehicle.color ?? "Not reported"} />
          <SpecRow label="Last annual test (date)" value={<span className="font-mono text-[13.5px]">{vehicle.last_test_date ?? "—"}</span>} />
          <SpecRow label="License valid until" value={<span className="font-mono text-[13.5px]">{vehicle.license_valid_until ?? "—"}</span>} />
        </dl>
        <p className="mt-1 text-[11.5px] text-ink-faint">The registry publishes the date of the last annual test, not its result.</p>
      </div>

      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
          {measured ? "Odometer · entered by a workshop" : "Mileage · machine-learning estimate (Model 1)"}
        </p>
        <dl className="border-t border-line">
          <SpecRow
            label={measured ? "Odometer (measured)" : "Estimated mileage"}
            tag={measured ? "MEASURED" : "ML"}
            value={<span className="font-mono text-[13.5px]">{km(mileage.primary_km)}</span>}
          />
          {!measured && (
            <SpecRow
              label="Indicative range (80%)"
              value={
                <span className="font-mono text-[13px] text-ink-soft">
                  {mileage.estimated_low_km.toLocaleString("en-US")} &ndash; {mileage.estimated_high_km.toLocaleString("en-US")} km
                </span>
              }
            />
          )}
        </dl>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{mileage.label}</p>
        {mileage.notes.length > 0 && (
          <ul className="mt-1.5 list-disc pl-5 text-[12px] text-ink-faint">
            {mileage.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
