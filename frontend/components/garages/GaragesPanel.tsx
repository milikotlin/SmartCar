"use client";

import { useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { ApiError, fetchGaragesInCity, fetchGaragesNear, searchCities, type GarageQuery } from "@/lib/api";
import { useFmt } from "@/lib/format";
import { GARAGE_SERVICES, type City, type GarageResults, type GarageService } from "@/lib/types";
import { Skeleton } from "../ui/Skeleton";
import { CardHeader, Tag } from "../ui/StatusPill";
import { CityCombobox } from "./CityCombobox";
import { GarageCard } from "./GarageCard";
import { GoogleDetailsPanel } from "./GoogleDetailsPanel";

const GarageMap = dynamic(() => import("./GarageMap").then((m) => m.GarageMap), { ssr: false, loading: () => <Skeleton className="h-full" /> });

const RADII = [5, 10, 20, 40];
const PAGE = 20;

type GeoError = "denied" | "unavailable" | "timeout" | "unsupported" | "outside";
type Place = { kind: "city"; city: City } | { kind: "gps"; position: { lat: number; lon: number } };
type State = { status: "idle" } | { status: "loading" } | { status: "error"; code: "registerDown" | "failed" } | { status: "ok"; results: GarageResults };

const field = "mt-1 h-12 w-full rounded-lg border-2 border-line-strong bg-paper px-3 text-[15px] font-semibold text-ink outline-none focus:border-accent";
const label = "text-[12px] font-bold uppercase tracking-wider text-ink-faint";

const ask = (p: Place, q: GarageQuery) => (p.kind === "city" ? fetchGaragesInCity(p.city.code, q) : fetchGaragesNear(p.position, q));

/** `electrified`: the vehicle on the screen is electric or hybrid (only a shortcut to that filter). */
export function GaragesPanel({ electrified }: { electrified: boolean }) {
  const t = useTranslations("garages");
  const locale = useLocale();
  const { num } = useFmt();
  const [popular, setPopular] = useState<City[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [radius, setRadius] = useState(10);
  const [service, setService] = useState<GarageService | "">("");
  const [state, setState] = useState<State>({ status: "idle" });
  const [loadingMore, setLoadingMore] = useState(false);
  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState<GeoError | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [ratingId, setRatingId] = useState<number | null>(null);
  const requestId = useRef(0); // only the answer to the last request reaches the screen

  useEffect(() => {
    searchCities("")
      .then(setPopular)
      .catch(() => setPopular([])); // the choice chips are optional: typing a city still works
  }, []);

  async function load(p: Place, radiusKm: number, svc: GarageService | "") {
    const id = ++requestId.current;
    setState({ status: "loading" });
    setActiveId(null);
    setRatingId(null);
    try {
      const results = await ask(p, { radiusKm, service: svc, limit: PAGE, offset: 0 });
      if (id === requestId.current) setState({ status: "ok", results });
    } catch (e) {
      if (id === requestId.current) setState({ status: "error", code: e instanceof ApiError && e.status === 503 ? "registerDown" : "failed" });
    }
  }

  async function loadMore(results: GarageResults) {
    if (!place) return;
    const id = requestId.current;
    setLoadingMore(true);
    try {
      const next = await ask(place, { radiusKm: radius, service, limit: PAGE, offset: results.items.length });
      if (id === requestId.current) setState({ status: "ok", results: { ...next, items: [...results.items, ...next.items] } });
    } catch {
      /* the list already on the screen stays; the button can be pressed again */
    } finally {
      setLoadingMore(false);
    }
  }

  function change(p: Place | null, radiusKm: number, svc: GarageService | "") {
    setPlace(p);
    setRadius(radiusKm);
    setService(svc);
    if (p) void load(p, radiusKm, svc);
  }

  function chooseCity(city: City) {
    setGeoError(null);
    change({ kind: "city", city }, radius, service);
  }

  /** Asked for only when the button is pressed; the browser then asks the user for permission. */
  function locate() {
    setGeoError(null);
    if (!("geolocation" in navigator)) {
      setGeoError("unsupported");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false);
        const position = { lat: Number(coords.latitude.toFixed(4)), lon: Number(coords.longitude.toFixed(4)) }; // about 10 m: enough to sort
        if (position.lat < 29 || position.lat > 33.6 || position.lon < 34 || position.lon > 36) setGeoError("outside");
        else change({ kind: "gps", position }, radius, service);
      },
      (e) => {
        setLocating(false);
        setGeoError(e.code === e.PERMISSION_DENIED ? "denied" : e.code === e.TIMEOUT ? "timeout" : "unavailable");
      },
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 60_000 },
    );
  }

  function select(id: number, scroll: boolean) {
    setActiveId(id);
    if (scroll) document.getElementById(`garage-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const results = state.status === "ok" ? state.results : null;
  const cityName = results?.city ? (locale === "he" ? results.city.name_he : results.city.name_en) : "";
  const rated = results?.items.find((g) => g.id === ratingId) ?? null;
  const chip = (on: boolean) =>
    `inline-flex min-h-9 items-center rounded-full border px-3 text-[12.5px] font-semibold transition-colors hover:border-accent hover:text-accent ${on ? "border-accent text-accent" : "border-line-strong bg-surface text-ink"}`;

  return (
    <section id="garages" className="card-shadow scroll-mt-32 rounded-2xl border border-line bg-surface p-6 max-[640px]:scroll-mt-4 max-[640px]:p-4" data-testid="garages">
      <CardHeader eyebrow={t("eyebrow")} title={t("title")} right={<Tag>{t("licensed")}</Tag>} />

      <div className="mt-4 grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,0.7fr)_auto] items-end gap-3 max-[900px]:grid-cols-2 max-[520px]:grid-cols-1">
        <div className="max-[900px]:col-span-2 max-[520px]:col-span-1">
          <CityCombobox selected={place?.kind === "city" ? place.city : null} onSelect={chooseCity} />
        </div>
        <label className={label}>
          {t("service")}
          <select value={service} data-testid="garage-service" onChange={(e) => change(place, radius, e.target.value as GarageService | "")} className={field}>
            <option value="">{t("allServices")}</option>
            {GARAGE_SERVICES.map((s) => (
              <option key={s} value={s}>
                {t(`services.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          {t("radius")}
          <select value={radius} data-testid="garage-radius" onChange={(e) => change(place, Number(e.target.value), service)} className={field}>
            {RADII.map((r) => (
              <option key={r} value={r}>
                {t("radiusValue", { km: r })}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={locate}
          disabled={locating}
          data-testid="garage-gps"
          className={`inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-lg border-2 px-4 text-[14px] font-bold transition-colors disabled:opacity-60 max-[900px]:col-span-2 max-[520px]:col-span-1 ${place?.kind === "gps" ? "border-accent bg-accent/10 text-accent" : "border-line-strong text-ink hover:border-accent hover:text-accent"}`}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-4 w-4" aria-hidden="true">
            <circle cx="12" cy="12" r="6" />
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
          </svg>
          {locating ? t("gpsBusy") : t("gps")}
        </button>
      </div>

      {(popular.length > 0 || electrified) && (
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label={t("popular")} role="group">
          <span className="text-[11.5px] font-bold uppercase tracking-wider text-ink-faint">{t("popular")}</span>
          {popular.map((c) => {
            const on = place?.kind === "city" && place.city.code === c.code;
            return (
              <button key={c.code} type="button" data-popular-city={c.code} aria-pressed={on} onClick={() => chooseCity(c)} className={chip(on)}>
                <bdi>{locale === "he" ? c.name_he : c.name_en}</bdi>
              </button>
            );
          })}
          {electrified && service !== "ev_hybrid" && (
            <button type="button" onClick={() => change(place, radius, "ev_hybrid")} className={chip(true)} data-testid="garage-ev-hint">
              {t("evHint")}
            </button>
          )}
        </div>
      )}

      {geoError && (
        <p role="alert" className="mt-4 rounded-lg border border-warn/50 bg-warn-bg px-4 py-3 text-[14px] font-semibold text-warn" data-testid="garage-geo-error">
          {t(`errors.${geoError}`)}
        </p>
      )}

      {state.status === "idle" && <p className="mt-5 rounded-xl border-2 border-dashed border-line-strong px-4 py-8 text-center text-[15px] font-semibold text-ink-soft">{t("idle")}</p>}

      {state.status === "loading" && (
        <div className="mt-5 grid grid-cols-2 gap-4 max-[1024px]:grid-cols-1" role="status" aria-label={t("loading")} data-testid="garage-loading">
          <Skeleton className="h-[420px]" />
          <Skeleton className="h-[420px] max-[1024px]:hidden" />
        </div>
      )}

      {state.status === "error" && (
        <div role="alert" className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-critical bg-critical-bg px-5 py-4" data-testid="garage-error">
          <p className="text-[15px] font-semibold text-critical">{t(`errors.${state.code}`)}</p>
          <button type="button" onClick={() => place && void load(place, radius, service)} className="min-h-11 rounded-lg border-2 border-critical px-4 text-[14px] font-bold text-critical">
            {t("retry")}
          </button>
        </div>
      )}

      {results && (
        <>
          <div className="mt-5 flex flex-col gap-1.5" aria-live="polite">
            {results.total > 0 && (
              <p className="text-[16px] font-bold text-ink" data-testid="garage-summary">
                {results.mode === "city"
                  ? t("summaryCity", { inCity: results.total_in_city ?? 0, city: cityName, around: results.total - (results.total_in_city ?? 0) })
                  : t("summaryGps", { total: results.total, km: results.radius_km })}
              </p>
            )}
            <p className="text-[13px] font-medium text-ink-soft" data-testid="garage-note">
              {results.approximate ? t("approximate", { city: cityName }) : t("gpsNote")}
            </p>
            {results.without_position > 0 && <p className="text-[12.5px] text-ink-faint">{t("withoutPosition", { count: results.without_position })}</p>}
            {results.stale && <p className="text-[12.5px] font-semibold text-warn">{t("stale", { date: results.as_of.slice(0, 10) })}</p>}
          </div>

          {results.total === 0 ? (
            <div className="mt-4 rounded-xl border-2 border-dashed border-line-strong px-4 py-8 text-center" data-testid="garage-empty">
              <p className="text-[16px] font-bold text-ink">{t("noResults")}</p>
              <p className="mt-1 text-[14px] text-ink-soft">{t("noResultsHint")}</p>
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-4 max-[1024px]:grid-cols-1">
              <ol className="relative flex max-h-[640px] flex-col gap-3 overflow-y-auto pe-1 max-[1024px]:order-2 max-[1024px]:max-h-none max-[1024px]:overflow-visible max-[1024px]:pe-0" data-testid="garage-list">
                {results.items.map((g, i) => (
                  <GarageCard key={g.id} garage={g} index={i + 1} active={g.id === activeId} ratings={results.ratings_available} onSelect={() => select(g.id, false)} onRating={() => setRatingId(g.id)} />
                ))}
                {results.items.length < results.total && (
                  <li>
                    <button
                      type="button"
                      disabled={loadingMore}
                      onClick={() => void loadMore(results)}
                      data-testid="garage-more"
                      className="min-h-12 w-full rounded-xl border-2 border-line-strong px-4 text-[14.5px] font-bold text-ink hover:border-accent hover:text-accent disabled:opacity-60"
                    >
                      {loadingMore ? t("loading") : t("more", { left: num(results.total - results.items.length) })}
                    </button>
                  </li>
                )}
              </ol>
              <div className="h-[640px] max-[1024px]:order-1 max-[1024px]:h-[340px]">
                {rated ? (
                  <GoogleDetailsPanel garage={rated} onClose={() => setRatingId(null)} />
                ) : (
                  <GarageMap garages={results.items} you={place?.kind === "gps" ? place.position : null} activeId={activeId} onSelect={(id) => select(id, true)} />
                )}
              </div>
            </div>
          )}
          <p className="mt-4 text-[12px] text-ink-faint">{t("source", { source: t("sourceName"), date: results.as_of.slice(0, 10) })}</p>
        </>
      )}
    </section>
  );
}
