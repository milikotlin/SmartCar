import { useLocale, useTranslations } from "next-intl";
import { useFmt } from "@/lib/format";
import type { Garage } from "@/lib/types";
import { Tag } from "../ui/StatusPill";

interface Props {
  garage: Garage;
  index: number;
  active: boolean;
  ratings: boolean;
  onSelect: () => void;
  onRating: () => void;
}

const action = "inline-flex min-h-11 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-3.5 text-[13.5px] font-bold transition-[filter,color,border-color]";

export function GarageCard({ garage, index, active, ratings, onSelect, onRating }: Props) {
  const t = useTranslations("garages");
  const locale = useLocale();
  const { num } = useFmt();
  return (
    <li
      id={`garage-${garage.id}`}
      data-testid="garage-card"
      data-position={garage.position}
      className={`rounded-xl border-2 p-4 transition-colors ${active ? "border-accent bg-accent/5" : "border-line bg-paper"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={onSelect} className="min-w-0 cursor-pointer text-start" aria-pressed={active}>
          <span className="flex items-baseline gap-2">
            <span className="font-mono text-[13px] font-bold text-accent">{index}</span>
            <bdi lang="he" className="text-[16px] font-bold leading-snug text-ink">
              {garage.name}
            </bdi>
          </span>
          <span className="mt-1 block text-[13.5px] text-ink-soft">
            {garage.address && (
              <>
                <bdi lang="he">{garage.address}</bdi>
                {" · "}
              </>
            )}
            <bdi>{locale === "he" ? garage.city_he : garage.city_en}</bdi>
          </span>
        </button>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {garage.distance_km !== null && <Tag tone="accent">{t(garage.position === "house" ? "distance" : "distanceApprox", { km: num(garage.distance_km, 1) })}</Tag>}
          {garage.in_city !== null && <Tag>{garage.in_city ? t("inCity") : t("nearby")}</Tag>}
        </div>
      </div>

      <p className="mt-2 text-[12.5px] text-ink-soft">{garage.services.map((s) => t(`services.${s}`)).join(" · ")}</p>
      <p className="mt-1 text-[12px] text-ink-faint">{t(`position.${garage.position}`)}</p>
      {garage.opening_hours && (
        <p className="mt-1 text-[12.5px] text-ink-soft">
          <span className="font-semibold text-ink">{t("hours")}:</span>{" "}
          <bdi dir="ltr" className="font-mono">
            {garage.opening_hours}
          </bdi>{" "}
          <span className="text-ink-faint">({t("hoursSource")})</span>
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <a href={garage.google_maps_url} target="_blank" rel="noopener noreferrer" aria-label={t("routeGoogle", { name: garage.name })} className={`${action} bg-accent text-accent-ink hover:brightness-110`}>
          {t("googleMaps")}
        </a>
        <a href={garage.waze_url} target="_blank" rel="noopener noreferrer" aria-label={t("routeWaze", { name: garage.name })} className={`${action} border-2 border-accent text-accent hover:brightness-110`}>
          {t("waze")}
        </a>
        {garage.phone && (
          <a href={`tel:${garage.phone.replace(/[^\d+*]/g, "")}`} className={`${action} border border-line-strong text-ink hover:border-accent hover:text-accent`}>
            <span className="sr-only">{t("call")}</span>
            <span dir="ltr" className="font-mono">
              {garage.phone}
            </span>
          </a>
        )}
        {ratings ? (
          <button type="button" onClick={onRating} className={`${action} border border-line-strong text-ink hover:border-accent hover:text-accent`} data-testid="garage-rating">
            {t("rating")}
          </button>
        ) : (
          <a href={garage.google_search_url} target="_blank" rel="noopener noreferrer" className={`${action} border border-line-strong text-ink-soft hover:border-accent hover:text-accent`}>
            {t("reviews")}
          </a>
        )}
      </div>
    </li>
  );
}
