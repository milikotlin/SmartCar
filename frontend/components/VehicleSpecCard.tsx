import type { ReactNode } from "react";
import type { VehicleProfile } from "@/lib/types";

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

export function VehicleSpecCard({ vehicle }: { vehicle: VehicleProfile }) {
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

      <dl className="border-t border-line">
        <SpecRow
          label="Manufacture year"
          value={<span className="font-mono text-[13.5px]">{vehicle.manufacture_year}</span>}
        />
        <SpecRow label="Fuel type" value={vehicle.fuel_type} />
        <SpecRow label="Ownership" value={vehicle.ownership} />
        <SpecRow label="Color" value={vehicle.color ?? "Not reported"} />
        <SpecRow
          label="Estimated mileage"
          tag="ML"
          value={<span className="font-mono text-[13.5px] text-ink-faint">Pending &mdash; Sprint 3</span>}
        />
        <SpecRow
          label="Last MOT test"
          value={<span className="font-mono text-[13.5px]">{vehicle.last_test_date ?? "—"}</span>}
        />
      </dl>
    </article>
  );
}
